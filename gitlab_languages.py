import argparse
import functools
import itertools
import json
import logging
import os
import multiprocessing
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import List, Dict, Tuple, Union
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
import gitlab
from gitlab.exceptions import GitlabGetError, GitlabAuthenticationError, GitlabHttpError
from gitlab.v4.objects import Group
from maya import MayaDT
from prometheus_client.core import CollectorRegistry, Gauge
from prometheus_client.exposition import write_to_textfile

logging.basicConfig(
    format="%(asctime)s - %(levelname)s " "- %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
"""{instance_url: {project_id: (last_activity_at, language_items)}}"""
language_cache: Union[
    None, Dict[str, Dict[int, Tuple[str, List[Dict[str, float]]]]]
] = None
gitlab_url = None
worker_count = multiprocessing.cpu_count() * 2


def error_wrapper(gen):
    while True:
        try:
            yield next(gen)
        except StopIteration:
            return
        except (GitlabGetError, GitlabHttpError):
            pass


def memoize(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        gl_project = args[1]
        project_id = str(gl_project.id)
        last_activity_current = gl_project.attributes["last_activity_at"]
        global language_cache
        if language_cache:
            projects = language_cache.get(gitlab_url)
        else:
            projects = dict()
            language_cache = dict()
        if projects.get(project_id):
            last_activity_cached, language_items = projects[project_id]
            last_activity_cached = MayaDT.from_iso8601(last_activity_cached)
            last_activity_current = MayaDT.from_iso8601(last_activity_current)

            if last_activity_cached >= last_activity_current:
                logger.debug(f"Using cache for project {gl_project.name}")
                return language_items

        """runs function normally, in-case no cache or cache is invalid"""
        languages = func(*args, **kwargs)
        """cache result"""
        projects[project_id] = (
            gl_project.attributes["last_activity_at"],
            list(languages),
        )
        language_cache[gitlab_url] = projects
        return languages

    return wrapper_decorator


class LanguageMetrics:
    def __init__(self, percentage):
        self.percentage = percentage
        self.total = 1

    def __add__(self, other):
        metric = LanguageMetrics(self.percentage + other.percentage)
        metric.total += 1
        return metric

    def __float__(self):
        return self.percentage

    def __str__(self):
        return str(self.percentage)


class MetricsCollector:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.metrics = dict()  # language_name, LanguageMetrics()

    def add(self, language_name, percentage):
        if self.metrics.get(language_name):
            self.metrics[language_name] += LanguageMetrics(percentage)
            logger.debug(f"Adding {percentage} to {language_name}")
        else:
            self.metrics[language_name] = LanguageMetrics(percentage)
            logger.debug(f"\tFound new language {language_name}")

    def write(
        self,
        path,
        groups_scanned=0,
        projects_scanned=0,
        projects_skipped=0,
        projects_no_language=0,
    ):
        total_languages = len(self.metrics.items())

        total_percent = sum([float(percent) for _, percent in self.metrics.items()])
        logger.debug(f"{total_percent}% total scanned")

        relative_languages = {
            language_name: (float(language) / projects_scanned)
            for language_name, language in self.metrics.items()
        }

        gauge = Gauge(
            "languages_percent",
            "Languages scanned in percent",
            labelnames=["language"],
            registry=self.registry,
        )

        language_items = relative_languages.items()

        for language_name, language in language_items:
            logger.info(f"Adding {language_name} as label")
            gauge.labels(language_name).set(round(language, 2))

        total_languages_scanned_gauge = Gauge(
            "languages_scanned_total", "Total languages scanned", registry=self.registry
        )
        total_languages_scanned_gauge.set(total_languages)

        project_scanned_gauge = Gauge(
            "projects_scanned_total", "Total projects scanned", registry=self.registry
        )
        project_scanned_gauge.set(projects_scanned)

        projects_skipped_gauge = Gauge(
            "projects_skipped_total", "Total projects skipped", registry=self.registry
        )
        projects_skipped_gauge.set(projects_skipped)

        projects_no_language_gauge = Gauge(
            "projects_no_language_total",
            "Projects without language detected",
            registry=self.registry,
        )
        projects_no_language_gauge.set(projects_no_language)

        groups_scanned_gauge = Gauge(
            "groups_scanned_total", "Total groups scanned", registry=self.registry
        )
        groups_scanned_gauge.set(groups_scanned)

        if Path(path).is_dir():
            path = Path(path) / "metrics.txt"
        if Path.exists(Path(path).parents[0]):
            write_to_textfile(path, self.registry)
            logger.info(f"Metrics written to {path}")
        else:
            logger.error(f"Could not write metrics to {path}")


class LanguageScanner:
    def __init__(self, gl_helper, ignored_projects: List[int] = None):
        self.gl_helper = gl_helper
        self.gl = gl_helper.gl
        self.metrics_collector = MetricsCollector()
        self.projects_scanned = 0
        self.groups_scanned = 0
        self.projects_skipped = 0
        self.projects_no_language = 0
        self.ignored_projects = ignored_projects

    @memoize
    def project_languages(self, gl_project):
        return gl_project.languages().items()

    def scan(self, gl_project):
        if self.ignored_projects and gl_project.id in self.ignored_projects:
            logger.info(f"Skipping project {gl_project.name}")
            self.projects_skipped += 1
            return
        logger.info(f"Scanning project {gl_project.name}")

        try:
            found = False
            for language_name, percentage in self.project_languages(gl_project):
                found = True
                self.metrics_collector.add(language_name, percentage)
            if found:
                self.projects_scanned += 1
            else:
                self.projects_no_language += 1
                logger.debug(f"\tNo language detected")
        except (GitlabGetError, GitlabHttpError) as e:
            self.projects_no_language += 1
            logger.debug(f"\tNo language detected")
            logger.error(e.error_message)

    def scan_group_projects(self, group_ids):
        for group_id in group_ids:
            try:
                group = self.gl.groups.get(group_id, simple=True)
            except GitlabGetError:
                logger.error(
                    f"Group with id {group_id} " f"does not exist or no access"
                )
                continue
            self.groups_scanned += 1
            projects = self.gl_helper.get_group_projects(group)
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                for project in error_wrapper(projects):
                    try:
                        project = self.gl.projects.get(project.id, simple=True)
                        executor.submit(self.scan, project)
                    except (GitlabGetError, GitlabHttpError):
                        continue

    def write_metrics(self, path=Path.cwd() / "metrics.txt"):
        self.metrics_collector.write(
            path=path,
            projects_scanned=self.projects_scanned,
            groups_scanned=self.groups_scanned,
            projects_skipped=self.projects_skipped,
            projects_no_language=self.projects_no_language,
        )

    def scan_projects(self, limit=None, args=None):
        if not args:
            args = {}

        projects = self.gl.projects.list(
            as_list=False, all_available=True, simple=True, **args
        )

        if limit:
            projects = itertools.islice(projects, limit)
            logger.info(f"Scanning a maximum of {limit} projects")
        else:
            logger.info(f"Scanning {projects.total} projects")

        if args:
            logger.info(f"with additional arguments {args}")

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for project in error_wrapper(projects):
                executor.submit(self.scan, project)


def check_env_variables():
    required_variables = ["GITLAB_ACCESS_TOKEN"]
    missing_variables = []
    [
        missing_variables.append(variable)
        for variable in required_variables
        if not os.getenv(variable)
    ]
    if len(missing_variables) > 0:
        exit(
            "Please set the required environment variables: {0}".format(
                ", ".join(missing_variables)
            )
        )


class GitLabHelper:
    def __init__(self, gl: gitlab.Gitlab):
        self.gl = gl

    def get_group_projects(self, root_group: Group):
        for project in root_group.projects.list(as_list=False):
            yield project
        for subgroup in root_group.subgroups.list(as_list=False):
            gl_group = self.gl.groups.get(subgroup.id)
            self.get_group_projects(gl_group)

    def get_subgroups(self, main_group):
        all_subgroups = main_group.subgroups.list(
            all=True, all_available=True, simple=True
        )
        for subgroup in all_subgroups:
            new_main = self.gl.groups.get(subgroup.id)
            yield new_main
            self.get_subgroups(new_main)

    def get_ignored_projects(self, group_ids: List[int]) -> List[int]:
        projects = list()
        logging.info("Parsing the ignored projects...")
        for group_id in group_ids:
            try:
                gl_group = self.gl.groups.get(group_id)
            except GitlabGetError:
                logging.error(f"Could not get group " f"with ID {group_id}. Skipping")
                continue

            sub_groups = self.get_subgroups(gl_group)
            for ignored_group in sub_groups:
                ignored_projects = ignored_group.projects.list(
                    as_list=False, all_available=True, simple=True
                )
                for ignored_project in ignored_projects:
                    logging.debug(
                        f"Adding {ignored_project.name} " f"to the ignored project list"
                    )
                    projects.append(ignored_project.id)
        logging.info(f"{len(projects)} projects will " f"be ignored and not scanned")
        return projects


def main():
    arg_parser = argparse.ArgumentParser("gitlab_languages")
    arg_parser.add_argument(
        "--project_limit",
        default=None,
        required=False,
        help="Set project limit to scan",
        type=int,
    )
    arg_parser.add_argument(
        "--args",
        default=None,
        required=False,
        help="Provide custom args to the GitLab API",
        nargs="+",
    )
    arg_parser.add_argument(
        "--groups",
        default=None,
        required=False,
        help="Scan only certain groups",
        nargs="+",
        type=int,
    )
    arg_parser.add_argument(
        "--ignore_groups",
        default=None,
        required=False,
        help="Ignore certain groups and their projects",
        nargs="+",
        type=int,
    )
    arg_parser.add_argument(
        "--cache", default=None, required=False, help="Cache file to use", type=str
    )
    arg_parser.add_argument(
        "-o",
        "--output",
        required=False,
        help="Location of the metrics file output",
        type=str,
        default=Path.cwd() / "metrics.txt",
    )

    arguments = vars(arg_parser.parse_args())
    check_env_variables()
    global gitlab_url
    gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
    logger.info(f"Running on {gitlab_url}")
    gl = gitlab.Gitlab(
        gitlab_url, private_token=os.getenv("GITLAB_ACCESS_TOKEN"), per_page=100
    )
    try:
        gl.auth()
    except GitlabAuthenticationError:
        exit(
            "You're not authorized to access this GitLab "
            "instance.\nPlease check your access token."
        )
    cache_file = arguments.get("cache")
    global language_cache
    if cache_file and os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            try:
                language_cache = json.load(f)
                logger.info("Cache loaded")
            except (UnicodeDecodeError, JSONDecodeError):
                logger.error("Could not restore cache")

    ignored_groups = arguments.get("ignore_groups")
    gl_helper = GitLabHelper(gl)
    ignored_projects = None
    if ignored_groups:
        ignored_projects = gl_helper.get_ignored_projects(ignored_groups)
    if ignored_groups:
        logger.info(
            f"Ignoring projects from group ids: "
            f"{', '.join(map(str, ignored_groups))}"
        )

    scanner = LanguageScanner(gl_helper, ignored_projects)
    additional_args = arguments.get("args")
    additional_args_dict = {}
    if additional_args:
        for pair in additional_args:
            entry = pair.split("=")
            additional_args_dict[entry[0]] = entry[1]

    project_limit = arguments.get("project_limit")
    project_limit = int(project_limit) if project_limit else None
    groups_to_scan = arguments.get("groups")

    if groups_to_scan:
        """scan only certain groups with id"""
        scanner.scan_group_projects(groups_to_scan)
    else:
        """scan everything"""
        scanner.scan_projects(limit=project_limit, args=additional_args_dict)
    scanner.write_metrics(path=arguments.get("output"))
    if cache_file:
        with open(cache_file, "w") as f:
            json.dump(language_cache, f, indent=2)
            logger.info("Cache saved")


if __name__ == "__main__":
    main()

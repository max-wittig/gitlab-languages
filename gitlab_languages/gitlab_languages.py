import argparse
import functools
import itertools
import json
import logging
import multiprocessing
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from json.decoder import JSONDecodeError
from pathlib import Path
from typing import Dict, List, Tuple, Union

import gitlab
from gitlab.exceptions import GitlabAuthenticationError, GitlabGetError, GitlabHttpError
from gitlab.v4.objects import Group
from maya import MayaDT
from prometheus_client.core import CollectorRegistry, Gauge
from prometheus_client.exposition import write_to_textfile

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Format: {instance_url: {project_id: (last_activity_at, language_items)}}
# A cached entry may also include repository_size as a third value.
language_cache: Union[
    None, Dict[str, Dict[int, Tuple[str, List[Dict[str, float]]]]]
] = None
gitlab_url = None
worker_count = os.getenv("WORKER_COUNT") or multiprocessing.cpu_count() * 2
worker_count = int(worker_count)
cache_lock = threading.Lock()

# GitLab's languages API returns percentages only. Weight those percentages by
# precomputed repository size so a tiny project does not count the same as a
# large one. `equal` keeps the historical per-project average.
WEIGHT_EQUAL = "equal"
WEIGHT_REPOSITORY_SIZE = "repository_size"
_ABSOLUTE_SIZE_KEYS = ("bytes", "size", "sloc", "lines", "line_count")
_PERCENT_KEYS = ("percentage", "share", "value")


def error_wrapper(gen):
    while True:
        try:
            yield next(gen)
        except StopIteration:
            return
        except (GitlabGetError, GitlabHttpError):
            pass


def _projects_cache():
    global language_cache
    if language_cache is None:
        language_cache = {}
    projects = language_cache.get(gitlab_url)
    if projects is None:
        projects = {}
        language_cache[gitlab_url] = projects
    return projects


def _cache_entry_current(entry, last_activity_at):
    if not entry or not last_activity_at:
        return False
    try:
        cached_activity = MayaDT.from_iso8601(entry[0])
        current_activity = MayaDT.from_iso8601(last_activity_at)
    except (TypeError, ValueError):
        # Includes pendulum.parsing.exceptions.ParserError, a ValueError subclass.
        return False
    return cached_activity >= current_activity


def cached_repository_size(project_id, last_activity_at):
    """Return a cached repository size when the project has not changed."""
    if not gitlab_url:
        return None
    with cache_lock:
        if not language_cache:
            return None
        projects = language_cache.get(gitlab_url) or {}
        entry = projects.get(str(project_id))
    if not entry or len(entry) < 3 or not _cache_entry_current(entry, last_activity_at):
        return None
    size = _coerce_number(entry[2])
    if size is None or size < 0:
        return None
    return int(size)


def remember_repository_size(project_id, size):
    """Store repository size next to cached languages, if that entry exists."""
    if size is None or not gitlab_url or language_cache is None:
        return
    with cache_lock:
        projects = language_cache.get(gitlab_url)
        if not projects:
            return
        entry = projects.get(str(project_id))
        if not entry:
            return
        projects[str(project_id)] = (entry[0], entry[1], int(size))


def memoize(func):
    @functools.wraps(func)
    def wrapper_decorator(*args, **kwargs):
        gl_project = args[1]
        project_id = str(gl_project.id)
        last_activity_current = gl_project.attributes["last_activity_at"]
        with cache_lock:
            projects = _projects_cache()
            cached = projects.get(project_id)
        if cached and _cache_entry_current(cached, last_activity_current):
            logger.debug(f"Using cache for project {gl_project.name}")
            return cached[1]

        """runs function normally, in-case no cache or cache is invalid"""
        languages = func(*args, **kwargs)
        """cache result"""
        with cache_lock:
            projects = _projects_cache()
            # Drop a stale size; scan() stores a fresh one after this returns.
            projects[project_id] = (
                gl_project.attributes["last_activity_at"],
                list(languages),
            )
        return languages

    return wrapper_decorator


def _coerce_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_language_value(value):
    """Return (percentage, absolute_size) from a languages API value.

    The public API currently returns a percentage. Absolute byte or line counts
    are used instead when a payload includes them.
    """
    if isinstance(value, dict):
        absolute = None
        for key in _ABSOLUTE_SIZE_KEYS:
            absolute = _coerce_number(value.get(key))
            if absolute is not None:
                break
        percentage = None
        for key in _PERCENT_KEYS:
            percentage = _coerce_number(value.get(key))
            if percentage is not None:
                break
        return percentage, absolute
    return _coerce_number(value), None


def project_language_contributions(language_items, project_weight):
    """Return ([(name, percentage, weight)], weight_used).

    Percentages are weighted by project size. An absolute per-language size is
    its own weight, so the overall figure is the share of that size.
    """
    parsed = [(name, *_parse_language_value(value)) for name, value in language_items]
    absolute_sizes = [size for _, _, size in parsed if size is not None and size > 0]
    if absolute_sizes:
        weight_used = float(sum(absolute_sizes))
        contributions = [
            (name, 100.0, size)
            for name, _, size in parsed
            if size is not None and size > 0
        ]
        return contributions, weight_used

    weight_used = (
        float(project_weight) if project_weight and project_weight > 0 else 1.0
    )
    contributions = [
        (name, percentage, weight_used)
        for name, percentage, _ in parsed
        if percentage is not None
    ]
    return contributions, weight_used


def repository_size_from_project(gl_project):
    """Return repository size in bytes, or None when statistics are absent."""
    attributes = getattr(gl_project, "attributes", None) or {}
    if not isinstance(attributes, dict):
        return None
    statistics = attributes.get("statistics")
    if not isinstance(statistics, dict):
        return None
    size = _coerce_number(statistics.get("repository_size"))
    if size is None or size < 0:
        return None
    return int(size)


class LanguageMetrics:
    def __init__(self, percentage, weight=1.0):
        self.percentage = float(percentage) * float(weight)
        self.weight = float(weight)
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
        self.total_weight = 0.0
        self._lock = threading.RLock()

    def add(self, language_name, percentage, weight=1.0):
        metric = LanguageMetrics(percentage, weight)
        with self._lock:
            if self.metrics.get(language_name):
                self.metrics[language_name] += metric
                logger.debug(f"Adding {percentage}*{weight} to {language_name}")
            else:
                self.metrics[language_name] = metric
                logger.debug(f"\tFound new language {language_name}")

    def record_project(self, language_items, project_weight=1.0):
        """Add one project's languages, weighted by project size."""
        contributions, weight_used = project_language_contributions(
            language_items, project_weight
        )
        if not contributions:
            return 0.0
        for language_name, percentage, weight in contributions:
            self.add(language_name, percentage, weight)
        with self._lock:
            self.total_weight += weight_used
        return weight_used

    def percentages(self, projects_scanned=0):
        divisor = self.total_weight if self.total_weight else (projects_scanned or 1)
        return {
            language_name: (float(language) / divisor)
            for language_name, language in self.metrics.items()
        }

    def write(
        self,
        path,
        groups_scanned=0,
        projects_scanned=0,
        projects_skipped=0,
        projects_no_language=0,
        repository_size_bytes=0,
        projects_missing_size=0,
        weight_mode=WEIGHT_EQUAL,
    ):
        total_languages = len(self.metrics.items())

        total_percent = sum([float(percent) for _, percent in self.metrics.items()])
        logger.debug(f"{total_percent} weighted points scanned")

        relative_languages = self.percentages(projects_scanned)

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

        repository_size_gauge = Gauge(
            "repository_size_bytes_total",
            "Sum of repository sizes in bytes used to weight language statistics",
            registry=self.registry,
        )
        repository_size_gauge.set(repository_size_bytes)

        projects_missing_size_gauge = Gauge(
            "projects_missing_size_total",
            "Projects without repository size, weighted as 1 byte",
            registry=self.registry,
        )
        projects_missing_size_gauge.set(projects_missing_size)

        if weight_mode == WEIGHT_REPOSITORY_SIZE:
            logger.info(
                "Weighted language statistics by repository size "
                f"({int(repository_size_bytes)} bytes, "
                f"{projects_missing_size} projects without a size)"
            )

        if Path(path).is_dir():
            path = Path(path) / "metrics.txt"
        if Path.exists(Path(path).parents[0]):
            write_to_textfile(path, self.registry)
            logger.info(f"Metrics written to {path}")
        else:
            logger.error(f"Could not write metrics to {path}")


class LanguageScanner:
    def __init__(
        self,
        gl_helper,
        ignored_projects: List[int] = None,
        weight: str = WEIGHT_REPOSITORY_SIZE,
    ):
        if weight not in (WEIGHT_EQUAL, WEIGHT_REPOSITORY_SIZE):
            raise ValueError(f"Unsupported weight mode: {weight}")
        self.gl_helper = gl_helper
        self.gl = gl_helper.gl
        self.metrics_collector = MetricsCollector()
        self.projects_scanned = 0
        self.groups_scanned = 0
        self.projects_skipped = 0
        self.projects_no_language = 0
        self.projects_missing_size = 0
        self.repository_size_bytes = 0
        self.ignored_projects = ignored_projects
        self.weight = weight
        self._lock = threading.Lock()
        self._missing_size_warned = False

    @memoize
    def project_languages(self, gl_project):
        return gl_project.languages().items()

    def _fetch_repository_size(self, gl_project):
        try:
            detailed = self.gl.projects.get(gl_project.id, statistics=True)
        except (GitlabGetError, GitlabHttpError) as exc:
            logger.debug(f"Could not load repository size for {gl_project.name}: {exc}")
            return None
        return repository_size_from_project(detailed)

    def _project_weight(self, gl_project):
        """Return (weight, known_bytes_or_none, size_was_missing)."""
        if self.weight != WEIGHT_REPOSITORY_SIZE:
            return 1.0, None, False

        size = repository_size_from_project(gl_project)
        if size is None:
            size = cached_repository_size(
                gl_project.id, gl_project.attributes.get("last_activity_at")
            )
        if size is None:
            size = self._fetch_repository_size(gl_project)

        if size is None:
            return 1.0, None, True
        if size <= 0:
            return 1.0, 0, False
        return float(size), int(size), False

    def _warn_missing_size_once(self):
        with self._lock:
            warn = not self._missing_size_warned
            self._missing_size_warned = True
        if warn:
            logger.warning(
                "Repository size is unavailable for at least one project. "
                "Those projects are weighted as 1 byte. "
                "Reading statistics requires the Reporter role. "
                "Use --weight equal to skip size lookups."
            )

    def scan(self, gl_project):
        if self.ignored_projects and gl_project.id in self.ignored_projects:
            logger.info(f"Skipping project {gl_project.name}")
            with self._lock:
                self.projects_skipped += 1
            return
        logger.info(f"Scanning project {gl_project.name}")

        try:
            languages = list(self.project_languages(gl_project))
            if not languages:
                with self._lock:
                    self.projects_no_language += 1
                logger.debug("\tNo language detected")
                return

            weight, known_bytes, missing = self._project_weight(gl_project)
            weight_used = self.metrics_collector.record_project(languages, weight)
            if not weight_used:
                with self._lock:
                    self.projects_no_language += 1
                logger.debug("\tNo language detected")
                return
            if known_bytes is not None:
                remember_repository_size(gl_project.id, known_bytes)
            with self._lock:
                self.projects_scanned += 1
                if known_bytes:
                    self.repository_size_bytes += known_bytes
                if missing:
                    self.projects_missing_size += 1
            if missing:
                self._warn_missing_size_once()
        except (GitlabGetError, GitlabHttpError) as e:
            with self._lock:
                self.projects_no_language += 1
            logger.debug("\tNo language detected")
            logger.error(e.error_message)

    def scan_group_projects(self, group_ids):
        for group_id in group_ids:
            try:
                group = self.gl.groups.get(group_id, simple=True)
            except GitlabGetError:
                logger.error(f"Group with id {group_id} does not exist or no access")
                continue
            self.groups_scanned += 1
            projects = self.gl_helper.get_group_projects(group)
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                for project in error_wrapper(projects):
                    try:
                        get_kwargs = (
                            {"statistics": True}
                            if self.weight == WEIGHT_REPOSITORY_SIZE
                            else {"simple": True}
                        )
                        project = self.gl.projects.get(project.id, **get_kwargs)
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
            repository_size_bytes=self.repository_size_bytes,
            projects_missing_size=self.projects_missing_size,
            weight_mode=self.weight,
        )

    def scan_projects(self, limit=None, args=None):
        if not args:
            args = {}

        projects = self.gl.projects.list(
            iterator=True,
            all_available=True,
            simple=True,
            pagination="keyset",
            order_by="id",
            **args,
        )

        if limit:
            projects = itertools.islice(projects, limit)
            logger.info(f"Scanning a maximum of {limit} projects")

        if self.weight == WEIGHT_REPOSITORY_SIZE:
            logger.info(
                "Weighting languages by repository size "
                "(statistics are requested when not already cached)"
            )

        if args:
            logger.info(f"with additional arguments {args}")

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            for project in error_wrapper(projects):
                executor.submit(self.scan, project)


def check_env_variables():
    if not os.getenv("GITLAB_ACCESS_TOKEN") and not os.getenv("GITLAB_TOKEN"):
        sys.exit("Please set GITLAB_TOKEN")


class GitLabHelper:
    def __init__(self, gl: gitlab.Gitlab):
        self.gl = gl

    def get_group_projects(self, root_group: Group):
        for project in root_group.projects.list(iterator=True):
            yield project
        for subgroup in root_group.subgroups.list(iterator=True):
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
                logging.error(f"Could not get group with ID {group_id}. Skipping")
                continue

            sub_groups = self.get_subgroups(gl_group)
            for ignored_group in sub_groups:
                ignored_projects = ignored_group.projects.list(
                    iterator=True, all_available=True, simple=True
                )
                for ignored_project in ignored_projects:
                    logging.debug(
                        f"Adding {ignored_project.name} to the ignored project list"
                    )
                    projects.append(ignored_project.id)
        logging.info(f"{len(projects)} projects will be ignored and not scanned")
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
        "--weight",
        default=WEIGHT_REPOSITORY_SIZE,
        choices=(WEIGHT_EQUAL, WEIGHT_REPOSITORY_SIZE),
        help=(
            "Weight projects in the overall language percentage. "
            "repository_size uses precomputed repository size in bytes "
            "(default). equal keeps the historical per-project average."
        ),
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
        gitlab_url,
        os.getenv("GITLAB_ACCESS_TOKEN") or os.getenv("GITLAB_TOKEN"),
        per_page=100,
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
            f"Ignoring projects from group ids: {', '.join(map(str, ignored_groups))}"
        )

    weight = arguments.get("weight") or WEIGHT_REPOSITORY_SIZE
    logger.info(f"Weighting projects by {weight}")
    scanner = LanguageScanner(gl_helper, ignored_projects, weight=weight)
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

# -*- coding: utf-8 -*-
import argparse
import os
import gitlab
from prometheus_client.core import CollectorRegistry, Gauge
from prometheus_client.exposition import write_to_textfile
import re
from gitlab.exceptions import GitlabGetError, GitlabAuthenticationError
import logging
import itertools
from pathlib import Path

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
log_level = logging.INFO
handler.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s - %(name)s '
                              '- %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(log_level)


def translate_language(lang):
    return lang.replace("#", "sharp")\
        .replace("+", "plus")\
        .replace("-", "minus")


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
            logger.debug(f"Adding {percentage} to {language_name}")  # noqa flake8 E999
        else:
            self.metrics[language_name] = LanguageMetrics(percentage)
            logger.info(f"Adding new language {language_name}")

    def write(self, groups_scanned=0, projects_scanned=0):
        total_languages = len(self.metrics.items())
        for language_name, language in self.metrics.items():
            logger.info(f"Adding {language_name} as Gauge")
            language_name = translate_language(language_name)
            language_name = re.sub("\W+", "", language_name)
            gauge = Gauge(language_name,
                          language_name,
                          registry=self.registry,
            )
            gauge.set(float(language) / total_languages)

        project_scanned_gauge = Gauge(
            "total_projects_scanned",
            "Total projects scanned",
            registry=self.registry,
        )
        project_scanned_gauge.set(projects_scanned)
        groups_scanned_gauge = Gauge(
            "total_groups_scanned",
            "Total groups scanned",
            registry=self.registry,
        )
        groups_scanned_gauge.set(groups_scanned)

        path = Path.cwd() / "metrics.txt"
        logger.info(f"Writing languages to {path}")
        write_to_textfile(path, self.registry)


class LanguageScanner:
    def __init__(self, gitlab_url, access_token):
        self.gl = gitlab.Gitlab(gitlab_url,
                                private_token=access_token)
        try:
            self.gl.auth()
        except GitlabAuthenticationError:
            exit("You're not authorized to access this GitLab "
                 "instance.\nPlease check your access token.")
        self.metrics_collector = MetricsCollector()
        self.projects_scanned = 0
        self.groups_scanned = 0

    def scan(self, gl_project):
        logger.info(f"Scanning project {gl_project.name}")
        self.projects_scanned += 1

        try:
            for language_name, percentage in gl_project.languages().items():
                self.metrics_collector.add(language_name, percentage)
        except GitlabGetError as e:
            logger.error(f"Failed to scan project {gl_project.name}")
            logger.debug(e.error_message)

    def scan_group_projects(self, group_ids, args):
        for group_id in group_ids:
            try:
                group = self.gl.groups.get(group_id)
            except GitlabGetError:
                logger.error(f"Group with id {group_id} does not exist "
                             f"or no access")
                continue

            self.groups_scanned += 1
            for project in group.projects.list(
                as_list=False,
                all_available=True,
                simple=True,
                **args
            ):
                project = self.gl.projects.get(project.id)
                self.scan(project)

        self.metrics_collector.write(
            projects_scanned=self.projects_scanned,
            groups_scanned=self.groups_scanned,
        )

    def scan_projects(self, limit=None, args=None):
        if not args:
            args = {}
        projects = self.gl.projects.list(
            as_list=False,
            all_available=True,
            **args
        )

        if limit:
            projects = itertools.islice(projects, limit)
            logger.info(f"Scanning a maximum of {limit} projects")
        else:
            logger.info("Scanning all projects")

        if args:
            logger.info(f"with additional arguments {args}")
        for project in projects:
            self.scan(project)
        self.metrics_collector.write(projects_scanned=self.projects_scanned)


def check_env_variables():
    required_variables = [
        "GITLAB_ACCESS_TOKEN",
    ]
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


def main():
    arg_parser = argparse.ArgumentParser("gitlab_languages")
    arg_parser.add_argument(
        "--projectlimit", default=None,
        required=False,
        help="Set project limit to scan",
        type=int,
    )
    arg_parser.add_argument(
        "--args", default=None,
        required=False,
        help="Provide custom args to the GitLab API",
        nargs="+",
    )
    arg_parser.add_argument(
        "--groups", default=None,
        required=False,
        help="Scan only certain groups",
        nargs="+",
    )

    arguments = vars(arg_parser.parse_args())
    check_env_variables()
    gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
    logger.info(f"Running on {gitlab_url}")
    scanner = LanguageScanner(
        gitlab_url,
        os.getenv("GITLAB_ACCESS_TOKEN")
    )
    additional_args = arguments.get("args")
    additional_args_dict = {}
    if additional_args:
        for pair in additional_args:
            entry = pair.split("=")
            additional_args_dict[entry[0]] = entry[1]

    project_limit = arguments.get("projectlimit")
    project_limit = int(project_limit) if project_limit else None
    groups_to_scan = arguments.get("groups")
    if groups_to_scan:
        """scan only certain groups with id"""
        scanner.scan_group_projects(
            groups_to_scan,
            args=additional_args_dict
        )
    else:
        """scan everything"""
        scanner.scan_projects(
            limit=project_limit,
            args=additional_args_dict
        )


if __name__ == "__main__":
    main()

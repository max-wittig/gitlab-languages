# -*- coding: utf-8 -*-
import argparse
import os
import gitlab
from prometheus_client import Gauge, CollectorRegistry, write_to_textfile
import re
from gitlab.exceptions import GitlabGetError


def translate_language(lang):
    return lang.replace("#", "sharp").replace("+", "plus")


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
        self.metrics = dict()  # language_name, Language()

    def add(self, language_name, percentage):
        if self.metrics.get(language_name):
            self.metrics[language_name] += LanguageMetrics(percentage)
        else:
            self.metrics[language_name] = LanguageMetrics(percentage)

    def write(self):
        total_languages = len(self.metrics.items())
        for language_name, language in self.metrics.items():
            language_name = translate_language(language_name)
            language_name = re.sub("\W+", "_", language_name)
            gauge = Gauge(language_name, language_name, registry=self.registry)
            gauge.set(float(language) / total_languages)
        write_to_textfile("metrics.txt", self.registry)


class LanguageScanner:
    def __init__(self, gitlab_url, access_token):
        self.gl = gitlab.Gitlab(gitlab_url, private_token=access_token)
        self.gl.auth()
        self.metrics_collector = MetricsCollector()

    def scan_all_projects(self):
        for project in self.gl.projects.list(as_list=False, owned=True):
            print(project.name)
            try:
                for language_name, percentage in project.languages().items():
                    self.metrics_collector.add(language_name, percentage)
            except GitlabGetError:
                pass
        self.metrics_collector.write()


def main():
    arg_parser = argparse.ArgumentParser("gitlab_languages")
    arg_parser.add_argument(
        "--instance-url", default="https://gitlab.com", required=False
    )
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
    # arguments = vars(arg_parser.parse_args())
    scanner = LanguageScanner("https://gitlab.com",
                              os.getenv("GITLAB_ACCESS_TOKEN"))
    scanner.scan_all_projects()


if __name__ == "__main__":
    main()

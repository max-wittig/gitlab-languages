#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open("README.md", "r") as readme_file:
    readme = readme_file.read()

requirements = ["prometheus_client>=0.6.0", "python-gitlab>=1.8.0", "maya>=0.6.1"]

setup_requirements = []

test_requirements = []

setup(
    author="Max Wittig",
    author_email="max.wittig95@gmail.com",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.7",
    ],
    description="Utility to generate a Prometheus data source "
    "text file for your GitLab repository "
    "using the GitLab Language API",
    install_requires=requirements,
    license="MIT license",
    long_description_content_type="text/markdown",
    long_description=readme,
    include_package_data=True,
    py_modules=["gitlab_languages"],
    entry_points={"console_scripts": ["gitlab_languages=gitlab_languages:main"]},
    keywords="gitlab_languages",
    name="gitlab_languages",
    packages=find_packages(include=["gitlab_languages"]),
    setup_requires=setup_requirements,
    tests_require=test_requirements,
    url="https://github.com/max-wittig/gitlab_languages",
    version="1.5.4",
    zip_safe=False,
    python_requires=">=3.7.0",
)

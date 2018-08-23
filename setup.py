#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = [
    "prometheus_client>=0.3.1",
    "python-gitlab>=1.5.1",
]

test_requirements = [
    "flake8==3.5.0",
    "pep8-naming==0.7.0",
]

setup(
    author="Max Wittig",
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ],
    description="Utility to generate a Prometheus data source "
                "text file for your GitLab repository "
                "using the GitLab Language API",
    install_requires=requirements,
    license="MIT license",
    long_description=readme,
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords='gitlab_languages',
    name='gitlab_languages',
    packages=find_packages(include=['gitlab_languages']),
    python_requires='>=3.6',
    test_suite='tests',
    tests_require=test_requirements,
    entry_points={
      'console_scripts': [
          'gitlab_languages = gitlab_languages.gitlab_languages:main'
      ]
    },
    url='https://github.com/max-wittig/gitlab_languages',
    version='1.0.0',
    zip_safe=False,
)

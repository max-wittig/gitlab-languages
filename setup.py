#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = []

setup_requirements = []

test_requirements = []

setup(
    author="Max Wittig",
    author_email='max.wittig95@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    description="Utility to list all languages in your "
                "GitLab instance, using the GitLab Language API",
    install_requires=requirements,
    license="MIT license",
    long_description=readme,
    include_package_data=True,
    keywords='gitlab_languages',
    name='gitlab_languages',
    packages=find_packages(include=['gitlab_languages']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/max-wittig/gitlab_languages',
    version='1.0.0',
    zip_safe=False,
)

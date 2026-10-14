# gitlab-languages

[![PyPI - License](https://img.shields.io/pypi/l/gitlab-languages.svg)](https://github.com/max-wittig/gitlab-languages/blob/master/LICENSE)

Utility to generate a Prometheus data source text file for your GitLab instance
using the [GitLab Language API](https://docs.gitlab.com/ee/api/projects.html#languages)

## installation from PyPI

1. Install from PyPI as CLI

   ```bash
   pip install -U gitlab-languages
   ```

1. Run the program

   ```bash
   gitlab-languages --cache cache.json --args owned=True # more info about usage: see below
   ```

## installation from source

1. Install python dependencies

    ```bash
    uv sync
    ```

1. Set the required environment variables

    ```bash
    export GITLAB_TOKEN=<SOME_TOKEN_WITH_API_SCOPE>
    export GITLAB_URL=https://gitlab.com # optional, defaults to https://gitlab.com
    # optional:
    export WORKER_COUNT=24
    ```

1. Run the tool

    ```bash
    gitlab-languages
    ```

## usage

```plain
usage: gitlab_languages [-h] [--project_limit PROJECT_LIMIT]
                        [--args ARGS [ARGS ...]]
                        [--groups GROUPS [GROUPS ...]]
                        [--ignore_groups IGNORE_GROUPS [IGNORE_GROUPS ...]]
                        [--cache CACHE] [--weight {equal,repository_size}]
                        [-o OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --project_limit PROJECT_LIMIT
                        Set project limit to scan
  --args ARGS [ARGS ...]
                        Provide custom args to the GitLab API
  --groups GROUPS [GROUPS ...]
                        Scan only certain groups
  --ignore_groups IGNORE_GROUPS [IGNORE_GROUPS ...]
                        Ignore certain groups and their projects
  --cache CACHE         Cache file to use
  --weight {equal,repository_size}
                        Weight projects in the overall language percentage.
                        repository_size uses precomputed repository size in
                        bytes (default). equal keeps the historical
                        per-project average.
  -o OUTPUT, --output OUTPUT
                        Location of the metrics file output
```

### project size

By default each project is weighted by its repository size. A repository with 10
lines of code no longer counts the same as a repository with 10,000 lines.

GitLab's languages API still returns only a percentage per language, not line
counts. Those percentages are already based on bytes, so each percentage is
weighted by the project's precomputed `statistics.repository_size`. GitLab
stores that size, so the tool does not have to walk the repository. If a future
languages payload includes absolute bytes or line counts, those values are used
directly.

Projects with no reported size are weighted as 1 byte. Pass `--weight equal` to
restore the previous average, where every project counts the same.

Reading repository size needs at least the Reporter role. When `--cache` is
set, the size is stored with the language data and is not requested again until
the project changes.

### additional arguments

You can specify additional arguments, that will be directly supplied to the
[python-gitlab library](https://github.com/python-gitlab/python-gitlab) or to the GitLab API endpoint.
Example:

```bash
gitlab-languages --args owned=True
```

More info about the available additional args can be found here:

* http://python-gitlab.readthedocs.io/en/stable/
* https://docs.gitlab.com/ee/api/

### example output

The output will look something like this:

```plain
metrics.txt

# HELP languages_percent Languages scanned in percent
# TYPE languages_percent gauge
languages_percent{language="Java"} 11.73
languages_percent{language="CSS"} 1.97
languages_percent{language="TypeScript"} 3.5
languages_percent{language="HTML"} 6.14
languages_percent{language="JavaScript"} 17.16
languages_percent{language="Python"} 10.4
languages_percent{language="Modelica"} 3.7
languages_percent{language="TeX"} 1.64
languages_percent{language="Shell"} 6.35
languages_percent{language="Batchfile"} 0.76
languages_percent{language="HCL"} 7.15
languages_percent{language="BitBake"} 0.56
languages_percent{language="C"} 5.25
languages_percent{language="C++"} 0.72
languages_percent{language="Matlab"} 2.77
languages_percent{language="TXL"} 0.05
languages_percent{language="Objective-C"} 1.48
languages_percent{language="XSLT"} 1.68
languages_percent{language="Perl"} 1.71
languages_percent{language="Ruby"} 0.03
languages_percent{language="C#"} 10.3
languages_percent{language="PowerShell"} 0.11
languages_percent{language="Pascal"} 0.01
languages_percent{language="ASP"} 0.0
languages_percent{language="PLpgSQL"} 0.0
languages_percent{language="Makefile"} 2.06
languages_percent{language="SQLPL"} 0.0
languages_percent{language="Puppet"} 0.0
languages_percent{language="Groovy"} 2.56
languages_percent{language="M4"} 0.01
languages_percent{language="Roff"} 0.15
languages_percent{language="CMake"} 0.01
languages_percent{language="NSIS"} 0.01
languages_percent{language="PHP"} 0.0
languages_percent{language="Go"} 0.0
languages_percent{language="Smalltalk"} 0.02
languages_percent{language="Visual Basic"} 0.0
languages_percent{language="Smarty"} 0.0
# HELP languages_scanned_total Total languages scanned
# TYPE languages_scanned_total gauge
languages_scanned_total 38.0
# HELP projects_scanned_total Total projects scanned
# TYPE projects_scanned_total gauge
projects_scanned_total 61.0
# HELP projects_skipped_total Total projects skipped
# TYPE projects_skipped_total gauge
projects_skipped_total 0.0
# HELP projects_no_language_total Projects without language detected
# TYPE projects_no_language_total gauge
projects_no_language_total 39.0
# HELP groups_scanned_total Total groups scanned
# TYPE groups_scanned_total gauge
groups_scanned_total 0.0
# HELP repository_size_bytes_total Sum of repository sizes in bytes used to weight language statistics
# TYPE repository_size_bytes_total gauge
repository_size_bytes_total 48233120.0
# HELP projects_missing_size_total Projects without repository size, weighted as 1 byte
# TYPE projects_missing_size_total gauge
projects_missing_size_total 2.0
```

Run the script via GitLab CI with schedules and export the metrics.txt file as GitLab pages.
Then you can add it to your Prometheus instance as scrape source.

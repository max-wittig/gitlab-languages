# gitlab_languages

Utility to generate a Prometheus data source text file for your GitLab instance
using the [GitLab Language API](https://docs.gitlab.com/ee/api/projects.html#languages)

![Demo](https://cdn.rawgit.com/max-wittig/gitlab_languages/master/images/termtosvg_jai2cshl.svg)

## installation from PyPI

1. Install from PyPI as program

   ```bash
   pip install -U gitlab-languages
   ```

1. Run the program

   ```bash
   gitlab_languages --args owned=True # more info about usage: see below
   ```

## installation from source

1. Install pipenv

    ```bash
    pip install pipenv
    ```

2. Install python dependencies

    ```bash
    pipenv install
    pipenv shell
    ```

3. Set the required environment variables

    ```bash
    export GITLAB_ACCESS_TOKEN=<SOME_TOKEN_WITH_API_SCOPE>
    export GITLAB_URL=https://gitlab.com # optional, defaults to https://gitlab.com
    ```

3. Run the script

    ```bash
    python gitlab_languages.py
    ```
 
## usage

```plain
usage: gitlab_languages [-h] [--projectlimit PROJECTLIMIT]
                        [--args ARGS [ARGS ...]]
                        [--groups GROUPS [GROUPS ...]]
                        [--ignore_groups IGNORE_GROUPS [IGNORE_GROUPS ...]]
                        [--cache CACHE]

optional arguments:
  -h, --help            show this help message and exit
  --projectlimit PROJECTLIMIT
                        Set project limit to scan
  --args ARGS [ARGS ...]
                        Provide custom args to the GitLab API
  --groups GROUPS [GROUPS ...]
                        Scan only certain groups
  --ignore_groups IGNORE_GROUPS [IGNORE_GROUPS ...]
                        Ignore certain groups and their projects
  --cache CACHE         Cache file to use
```

### additional arguments

You can specify additional arguments, that will be directly supplied to the
[python-gitlab library](https://github.com/python-gitlab/python-gitlab) or to the GitLab API endpoint.
Example:

```bash
python3 gitlab_languages --args owned=True
``` 

More info about the available additional args can be found here:

* http://python-gitlab.readthedocs.io/en/stable/
* https://docs.gitlab.com/ce/api/

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
```

Run the script via GitLab CI with schedules and export the metrics.txt file as GitLab pages.
Then you can add it to your Prometheus instance as scrape source.

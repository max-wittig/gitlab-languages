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

```
usage: gitlab_languages [-h] [--projectlimit PROJECTLIMIT]
                        [--args ARGS [ARGS ...]]
                        [--groups GROUPS [GROUPS ...]]
                        [--ignore_groups IGNORE_GROUPS [IGNORE_GROUPS ...]]

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

# HELP total_unknown_languages Unknown languages
# TYPE total_unknown_languages gauge
total_unknown_languages 0.0
# HELP Ruby Ruby
# TYPE Ruby gauge
Ruby 1.6042222222222224
# HELP JavaScript JavaScript
# TYPE JavaScript gauge
JavaScript 16.529111111111114
# HELP HTML HTML
# TYPE HTML gauge
HTML 4.456222222222222
# HELP Vue Vue
# TYPE Vue gauge
Vue 0.08822222222222223
# HELP CSS CSS
# TYPE CSS gauge
CSS 0.851111111111111
# HELP Shell Shell
# TYPE Shell gauge
Shell 0.22911111111111107
# HELP Clojure Clojure
# TYPE Clojure gauge
Clojure 0.0
# HELP Python Python
# TYPE Python gauge
Python 35.05222222222222
# HELP TeX TeX
# TYPE TeX gauge
TeX 6.637777777777777
# HELP Java Java
# TYPE Java gauge
Java 22.18177777777778
# HELP Rust Rust
# TYPE Rust gauge
Rust 2.2222222222222223
# HELP PHP PHP
# TYPE PHP gauge
PHP 3.172888888888889
# HELP Kotlin Kotlin
# TYPE Kotlin gauge
Kotlin 2.2064444444444447
# HELP Hack Hack
# TYPE Hack gauge
Hack 1.830888888888889
# HELP TypeScript TypeScript
# TYPE TypeScript gauge
TypeScript 1.456888888888889
# HELP C C
# TYPE C gauge
C 0.5948888888888889
# HELP PLSQL PLSQL
# TYPE PLSQL gauge
PLSQL 0.4702222222222222
# HELP Cplusplus Cplusplus
# TYPE Cplusplus gauge
Cplusplus 0.3168888888888889
# HELP Makefile Makefile
# TYPE Makefile gauge
Makefile 0.03488888888888889
# HELP Roff Roff
# TYPE Roff gauge
Roff 0.02711111111111111
# HELP Perl Perl
# TYPE Perl gauge
Perl 0.018666666666666665
# HELP M4 M4
# TYPE M4 gauge
M4 0.008222222222222223
# HELP Csharp Csharp
# TYPE Csharp gauge
Csharp 0.005111111111111111
# HELP Pascal Pascal
# TYPE Pascal gauge
Pascal 0.0011111111111111111
# HELP ASP ASP
# TYPE ASP gauge
ASP 0.0006666666666666666
# HELP NSIS NSIS
# TYPE NSIS gauge
NSIS 0.0006666666666666666
# HELP Ada Ada
# TYPE Ada gauge
Ada 0.0006666666666666666
# HELP CMake CMake
# TYPE CMake gauge
CMake 0.00044444444444444447
# HELP PureBasic PureBasic
# TYPE PureBasic gauge
PureBasic 0.00044444444444444447
# HELP PLpgSQL PLpgSQL
# TYPE PLpgSQL gauge
PLpgSQL 0.00022222222222222223
# HELP ObjectiveminusC ObjectiveminusC
# TYPE ObjectiveminusC gauge
ObjectiveminusC 0.00022222222222222223
# HELP SQLPL SQLPL
# TYPE SQLPL gauge
SQLPL 0.0
# HELP total_languages_scanned Total languages scanned
# TYPE total_languages_scanned gauge
total_languages_scanned 32.0
# HELP total_projects_scanned Total projects scanned
# TYPE total_projects_scanned gauge
total_projects_scanned 45.0
# HELP total_projects_skipped Total projects skipped
# TYPE total_projects_skipped gauge
total_projects_skipped 3.0
# HELP total_groups_scanned Total groups scanned
# TYPE total_groups_scanned gauge
total_groups_scanned 0.0
```

Run the script via GitLab CI with schedules.
Then you can add it to your Prometheus instance as data source.

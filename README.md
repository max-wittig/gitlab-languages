# gitlab_languages

Utility to generate a Prometheus data source text file for your GitLab instance
using the [GitLab Language API](https://docs.gitlab.com/ee/api/projects.html#languages)

![Demo](https://cdn.rawgit.com/max-wittig/gitlab_languages/master/images/termtosvg_jai2cshl.svg)

## installation

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
    export GITLAB_URL=https://gitlab.com
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

```
metrics.txt

# HELP total_unknown_languages Unknown languages
# TYPE total_unknown_languages gauge
total_unknown_languages 0.0
# HELP Python Python
# TYPE Python gauge
Python 21.790000000000003
# HELP CSS CSS
# TYPE CSS gauge
CSS 8.503333333333334
# HELP SaltStack SaltStack
# TYPE SaltStack gauge
SaltStack 1.95
# HELP JavaScript JavaScript
# TYPE JavaScript gauge
JavaScript 0.9533333333333333
# HELP PLpgSQL PLpgSQL
# TYPE PLpgSQL gauge
PLpgSQL 0.7666666666666666
# HELP Mako Mako
# TYPE Mako gauge
Mako 0.03333333333333333
# HELP Shell Shell
# TYPE Shell gauge
Shell 0.03
# HELP Java Java
# TYPE Java gauge
Java 30.776666666666667
# HELP HTML HTML
# TYPE HTML gauge
HTML 1.8666666666666665
# HELP Arduino Arduino
# TYPE Arduino gauge
Arduino 33.333333333333336
# HELP total_languages_scanned Total languages scanned
# TYPE total_languages_scanned gauge
total_languages_scanned 10.0
# HELP total_projects_scanned Total projects scanned
# TYPE total_projects_scanned gauge
total_projects_scanned 3.0
# HELP total_projects_skipped Total projects skipped
# TYPE total_projects_skipped gauge
total_projects_skipped 7.0
# HELP total_groups_scanned Total groups scanned
# TYPE total_groups_scanned gauge
total_groups_scanned 0.0
```

Run the script via GitLab API with schedules.
Then you can add it to your Prometheus instance as data source.

# gitlab_languages

Utility to generate a Prometheus data source text file for your GitLab instance
using the [GitLab Language API](https://docs.gitlab.com/ee/api/projects.html#languages)

## installation

1. Install python virtualenv

    ```bash
    python3 -m venv venv
    ```

2. Install python dependencies

    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3. Set the required environment variables
    ```bash
    export GITLAB_ACCESS_TOKEN=<SOME_TOKEN_WITH_API_SCOPE>
    export GITLAB_URL=https://gitlab.com
    ```

3. Run the script

    ```bash
    python3 gitlab_languages.py
    ```
 
## usage

```
usage: gitlab_languages [-h] [--projectlimit PROJECTLIMIT]
                        [--args ARGS [ARGS ...]]
                        [--groups GROUPS [GROUPS ...]]

optional arguments:
  -h, --help            show this help message and exit
  --projectlimit PROJECTLIMIT
                        Set project limit to scan
  --args ARGS [ARGS ...]
                        Provide custom args to the GitLab API
  --groups GROUPS [GROUPS ...]
                        Scan only certain groups, separated by space
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

# HELP JavaScript JavaScript
# TYPE JavaScript gauge
JavaScript 28.93833333333334
# HELP HTML HTML
# TYPE HTML gauge
HTML 28.308888888888887
# HELP CSS CSS
# TYPE CSS gauge
CSS 10.09
# HELP C C
# TYPE C gauge
C 4.957777777777777
# HELP Cplusplus Cplusplus
# TYPE Cplusplus gauge
Cplusplus 0.5605555555555556
# HELP Makefile Makefile
# TYPE Makefile gauge
Makefile 0.02888888888888889
# HELP Shell Shell
# TYPE Shell gauge
Shell 0.008333333333333333
# HELP Java Java
# TYPE Java gauge
Java 33.333333333333336
# HELP Csharp Csharp
# TYPE Csharp gauge
Csharp 16.558888888888887
# HELP total_projects_scanned Total projects scanned
# TYPE total_projects_scanned counter
total_projects_scanned 35.0
```

Run the script via GitLab API with schedules.
Then you can add it to your Prometheus instance as data source.

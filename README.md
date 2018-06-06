# gitlab_languages

Utility to list the languages in your GitLab repository
using the GitLab Language API

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
    ```

3. Run the script

    ```bash
    python3 gitlab_languages.py
    ```
 

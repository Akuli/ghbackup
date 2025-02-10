## Setup

```
$ python3 -m venv env
$ source env/bin/activate
$ pip install -r requirements.txt
```


## Usage

Create an empty directory, and place a file named `info.txt` in it with the following content:

```
GitHub URL: https://github.com/Akuli/jou
```

(or whatever repository you want to back up).
Then run:

```
$ python3 ghbackup.py path/to/folder_that_contains_info_dot_txt
```

This will copy all issue and pull request comments from GitHub to your local folder.

If you get rate limit errors,
you can either run the same command again later (will continue where it left off, not start from scratch).
Alternatively, you can pass a GitHub token:

```
$ python3 ghbackup.py path/to/folder_that_contains_info_dot_txt --token $(cat my_secret_token.txt)
```

This assumes you have saved your GitHub token to file `my_secret_token.txt`.
I don't recommend copy/pasting the token directly to command line,
because the token may get saved in your bash history or similar.


## Developing

Running mypy (type checker):

```
$ source env/bin/activate
$ pip install -r requirements-dev.txt
$ mypy ghbackup.py
```

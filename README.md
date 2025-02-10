Setup and run:

```
$ python3 -m venv env
$ source env/bin/activate
$ pip install -r requirements.txt
$ python3 ghbackup.py https://github.com/Akuli/jou ./backups/jou
```

If you get rate limit issues, you can pass a GitHub token:

```
$ python3 ghbackup.py https://github.com/Akuli/jou ./backups/jou --token $(cat my_secret_token.txt)
```

This assumes you have saved your GitHub token to file `my_secret_token.txt`.
I don't recommend copy/pasting the token directly to command line (except in scripts or GitHub Actions),
because the token may get saved in your bash history or similar.


## Developing

Running mypy (type checker):

```
$ source env/bin/activate
$ pip install -r requirements-dev.txt
$ mypy ghbackup.py
```

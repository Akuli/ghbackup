# GitHub Backups

This is a Python script that downloads comments from GitHub.
This way you can look at GitHub issues and pull requests of your projects
even if GitHub is down or your internet doesn't work.

**This script does not download the content of the repository itself, only issue and PR comments.**
That would be unnecessary, because by design, Git repositories are difficult to delete accidentally:
every developer has a local clone of the whole repository.


## Usage

Create a new directory, and place a file named `info.txt` in it with the following content:

```
GitHub URL: https://github.com/Akuli/jou
```

(or whatever repository you want to back up). Then run:

```
$ pip install requests
$ python3 ghbackup.py path/to/folder_that_contains_info_dot_txt
```

This will copy all issue and pull request comments from GitHub to your local folder.

If you get rate limit errors, you can simply run the same command again later
(will continue where it left off, not start from scratch).
Alternatively, you can specify a GitHub API token.
Requests with an API token have higher rate limits than requests without.

```
$ python3 ghbackup.py path/to/folder_that_contains_info_dot_txt --token $(cat my_secret_token.txt)
```

This assumes you have saved your GitHub token to file `my_secret_token.txt`.
I don't recommend copy/pasting the token directly to command line,
because the token may get saved in your bash history or similar.


## File Structure

GitHub returns everything as JSON.
This script converts GitHub's JSONs into a file structure
that is human-readable and easy to parse.
For example, you can commit the results to Git and get reasonable `git diff` output.

Once the script has ran, the backup folder will look something like this:

```
$ ls
info.txt     issue_00024  issue_00051  issue_00084  pr_00014  pr_00035  pr_00059  pr_00079
issue_00002  issue_00026  issue_00052  issue_00085  pr_00016  pr_00036  pr_00061  pr_00080
issue_00003  issue_00029  issue_00056  issue_00086  pr_00017  pr_00037  pr_00062  pr_00089
issue_00004  issue_00031  issue_00060  issue_00087  pr_00019  pr_00038  pr_00063  pr_00090
issue_00005  issue_00032  issue_00065  issue_00088  pr_00020  pr_00039  pr_00064  pr_00092
issue_00006  issue_00040  issue_00070  issue_00091  pr_00021  pr_00043  pr_00066  pr_00094
issue_00008  issue_00041  issue_00071  issue_00093  pr_00022  pr_00046  pr_00067  pr_00095
issue_00011  issue_00042  issue_00074  issue_00097  pr_00025  pr_00047  pr_00068  pr_00096
issue_00012  issue_00044  issue_00077  issue_00098  pr_00027  pr_00053  pr_00069  pr_00099
issue_00013  issue_00045  issue_00078  pr_00001     pr_00028  pr_00054  pr_00072
issue_00015  issue_00048  issue_00081  pr_00007     pr_00030  pr_00055  pr_00073
issue_00018  issue_00049  issue_00082  pr_00009     pr_00033  pr_00057  pr_00075
issue_00023  issue_00050  issue_00083  pr_00010     pr_00034  pr_00058  pr_00076
```

The content of `info.txt` is:

```
GitHub URL: https://github.com/Akuli/jou
Updated: 2025-02-10 22:19:28.145222+00:00
```

Each `issue_xxxxx` and `pr_xxxxx` is a subfolder.

```
$ cd issue_00077/
$ ls
0001_Akuli.txt  0002_Moosems.txt  0003_Akuli.txt  0004_Akuli.txt  0005_Akuli.txt  info.txt
```

The content of `issue_xxxxx/info.txt` or `pr_xxxxx/info.txt` looks like this:

```
$ cat info.txt
Title: Jou package manager?
Updated: 2025-01-26T18:25:08+00:00
```

Other files in the subfolders represent comments on the issue or PR, and they look e.g. like this:

```
$ cat 0002_Moosems.txt
GitHub ID: 1868421964
Author: Moosems
Created: 2023-12-24T03:13:38Z

Any thoughts on the package manager?
```


## Deploying

I configured a server to run this script periodically.

On remote server, create an account, and set permissions so that you can add files to its home folder:

```
$ sudo apt install python3-requests
$ sudo adduser --system ghbackup
$ sudo chown ghbackup:$USER /home/ghbackup
$ sudo chmod g+w /home/ghbackup
```

Locally:

```
$ scp ghbackup.py my_remote_server:/home/ghbackup/ghbackup.py
$ scp ghbackup.service my_remote_server:/tmp/
```

On remote server: (using `ghbackup$` to denote a shell running as `ghbackup` user)

```
$ sudo -u ghbackup bash
ghbackup$ cd
ghbackup$ umask 0022                # create readable directories and files
ghbackup$ git init backups
ghbackup$ cd backups
ghbackup$ git config user.name "backup bot"
ghbackup$ git config user.email "whatever@example.com"
ghbackup$ exit
$ cat /tmp/ghbackup.service | sudo tee /etc/systemd/system/ghbackup.service
$ rm /tmp/ghbackup.service
$ sudo systemctl enable ghbackup
$ sudo systemctl start ghbackup
$ sudo systemctl status ghbackup
```

Now adding a new directory to back up is as simple as creating a folder with `info.txt`:

```
$ sudo -u ghbackup bash -c 'cd /home/ghbackup/backups && mkdir jou && echo "GitHub URL: https://github.com/Akuli/jou" > jou/info.txt'
```

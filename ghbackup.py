from __future__ import annotations
import argparse
import re
from typing import Any
from datetime import datetime, timezone, timedelta
from collections.abc import Iterator
from pathlib import Path

import requests


session = requests.Session()

# These are optional, but GitHub recommends setting them
session.headers["Accept"] = "application/vnd.github+json"
session.headers["X-GitHub-Api-Version"] = "2022-11-28"


def issues_and_prs(owner: str, repo: str, since: datetime | None) -> Iterator[dict[str, Any]]:
    query_params: dict[str, Any] = {
        "state": "all",  # open and closed
        "page": 1,
        "per_page": 100,
    }
    if since is not None:
        assert since.tzinfo == timezone.utc
        query_params["since"] = since.isoformat(timespec='seconds')

    while True:
        r = session.get(f"https://api.github.com/repos/{owner}/{repo}/issues", params=query_params)
        r.raise_for_status()

        results: list[dict[str, Any]] = r.json()
        if not results:
            # End of list
            break

        for result in results:
            yield result
        query_params["page"] += 1


def iter_comments(issue_or_pr: dict[str, Any], since: datetime | None) -> Iterator[dict[str, Any]]:
    yield issue_or_pr  # The issue/pr JSON itself has same fields that comments have

    if issue_or_pr["comments"] != 0:
        query_params: dict[str, Any] = {"page": 1, "per_page": 100}
        if since is not None:
            assert since.tzinfo == timezone.utc
            query_params["since"] = since.isoformat(timespec='seconds')

        while True:
            r = session.get(issue_or_pr["comments_url"], params=query_params)
            r.raise_for_status()

            results: list[dict[str, Any]] = r.json()
            if not results:
                # End of list
                break

            for result in results:
                yield result
            query_params["page"] += 1


def save_comment(comment: dict[str, Any], folder: Path) -> None:
    # TODO: use comment["reactions"]
    author = comment["user"]["login"]
    next_number = 1
    number = None

    for path in folder.iterdir():
        if not path.is_file():
            continue

        m = re.fullmatch(r"(\d+)_(.*)\.txt", path.name)
        if not m:
            continue

        next_number = max(int(m.group(1)) + 1, next_number)

        if m.group(2) == author:
            with path.open("r", encoding="utf-8") as file:
                if file.readline() == f"GitHub ID: {comment['id']}\n":
                    number = int(m.group(1))
                    print(f"      Comment number {number} from {author} has been edited, overwriting")
                    path.unlink()
                    break

    if number is None:
        number = next_number
        print(f"      New comment number {number} from {author}")

    file_path = folder / f"{number:04}_{author}.txt"

    with file_path.open("w", encoding="utf-8") as file:
        file.write(f"GitHub ID: {comment['id']}\n")
        file.write(f"Author: {author}\n")
        file.write(f"Created: {comment['created_at']}\n")
        file.write("\n")

        # Fix GitHub weirdness:
        #  - issue description/body may be null
        #  - issue description/body does not necessarily end with \n
        body = comment["body"] or ""
        if not body.endswith("\n"):
            body += "\n"
        file.write(body)


def update_repo(repo_folder: Path) -> None:
    start_time = datetime.now(timezone.utc)
    repo_info_txt = repo_folder / "info.txt"
    since = None
    github_url = None

    with repo_info_txt.open("r") as file:
        line = file.readline()
        assert line.startswith("GitHub URL: "), line
        github_url = line.split(": ")[1].strip()
        print(f"Backing up issue and PR comments: {github_url} --> {repo_folder}")

        for line in file:
            if line.startswith("Updated: "):
                since = datetime.fromisoformat(line.split(": ")[1].strip())
                since -= timedelta(minutes=10)  # in case clocks are out of sync
                print(f"  Updating only what has changed since {since}.")

    m = re.fullmatch(r"https://github.com/([^/]+)/([^/]+)", github_url)
    if not m:
        raise ValueError(f"bad GitHub URL: {github_url!r}")
    user, reponame = m.groups()

    for issue_or_pr in issues_and_prs(user, reponame, since):
        if "pull_request" in issue_or_pr:
            print(f"  Found PR #{issue_or_pr['number']}: {issue_or_pr['title']}")
            issue_or_pr_folder = repo_folder / f"pr_{issue_or_pr['number']:05}"
        else:
            print(f"  Found issue #{issue_or_pr['number']}: {issue_or_pr['title']}")
            issue_or_pr_folder = repo_folder / f"issue_{issue_or_pr['number']:05}"

        issue_or_pr_folder.mkdir(exist_ok=True)

        last_updated = None
        try:
            with (issue_or_pr_folder / "info.txt").open("r") as file:
                for line in file:
                    if line.startswith("Updated: "):
                        last_updated = datetime.fromisoformat(line.split(": ")[1].strip())
                        break
        except FileNotFoundError:
            pass

        if datetime.fromisoformat(issue_or_pr["updated_at"]) == last_updated:
            print("    Already up to date")
            continue

        for comment in iter_comments(issue_or_pr, since):
            print(f"    Found comment from {comment['user']['login']}")
            save_comment(comment, issue_or_pr_folder)

        # Write info after all comments, so that the issue or pull request
        # is not considered to be up-to-date if something errors
        with (issue_or_pr_folder / "info.txt").open("w") as file:
            file.write(f"Title: {issue_or_pr['title']}\n")
            file.write(f"Updated: {issue_or_pr['updated_at']}\n")

    with repo_info_txt.open("w") as file:
        file.write(f"GitHub URL: {github_url}\n")
        file.write(f"Updated: {start_time}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folders", nargs=argparse.ONE_OR_MORE, help="Folders that contain info.txt with GitHub URL (see README)")
    parser.add_argument("--token", help="Github API token (optional, but helps with rate limit issues)")
    args = parser.parse_args()

    if args.token is not None:
        session.headers["Authorization"] = f"Token {args.token}"

    for repo_folder in args.folders:
        update_repo(Path(repo_folder))


main()

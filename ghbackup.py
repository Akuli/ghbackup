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


def set_token(token: str) -> None:
    """Authenticate all future requests with given token to prevent rate limit issues"""
    session.headers["Authorization"] = f"Token {token}"


class Repo:
    def __init__(self, owner: str, repo: str) -> None:
        self.owner = owner
        self.repo = repo

    def issues_and_prs(self, since: datetime | None) -> Iterator[Issue | PR]:
        query_params: dict[str, Any] = {
            "state": "all",  # open and closed
            "page": 1,
            "per_page": 100,
        }
        if since is not None:
            assert since.tzinfo == timezone.utc
            query_params["since"] = since.isoformat(timespec='seconds')

        while True:
            r = session.get(f"https://api.github.com/repos/{self.owner}/{self.repo}/issues", params=query_params)
            r.raise_for_status()

            results: list[dict[str, Any]] = r.json()
            if not results:
                # End of list
                break

            for issue_or_pr in results:
                if "pull_request" in issue_or_pr:
                    yield PR(issue_or_pr)
                else:
                    yield Issue(issue_or_pr)
            query_params["page"] += 1


class Comment:
    def __init__(self, github_json: dict[str, Any]):
        self.github_id: int = github_json["id"]
        self.text: str = github_json["body"] or ""
        self.author_username: str = github_json["user"]["login"]

        # Do not track edits of comments, because there is no way to check
        # whether/when the first comment of an issue or PR has been edited. The
        # updated_at field doesn't work, because it changes whenever the issue
        # or PR receives any activity.
        self.created = datetime.fromisoformat(github_json["created_at"])

        # TODO: github_json["reactions"]



# Internal base class
class _IssueOrPR:
    def __init__(self, github_json: dict[str, Any]) -> None:
        if type(self) is _IssueOrPR:
            raise RuntimeError("_IssueOrPR cannot be instantiated directly, instantiate Issue or PR instead")

        # The JSON has same fields that comments have
        self._initial_comment = Comment(github_json)

        self._comments_other_than_initial_count: int = github_json["comments"]
        self._comments_url = github_json["comments_url"]

        self.title: str = github_json["title"]
        self.number: int = github_json["number"]

        # The "created_at" field is in the initial comment
        self.updated = datetime.fromisoformat(github_json["updated_at"])

    def __repr__(self) -> str:
        # Example: <issue #123>
        return f"<{type(self).__name__} #{self.number}>"

    def iter_comments(self, since: datetime | None) -> Iterator[Comment]:
        yield self._initial_comment

        if self._comments_other_than_initial_count != 0:
            query_params: dict[str, Any] = {"page": 1, "per_page": 100}
            if since is not None:
                assert since.tzinfo == timezone.utc
                query_params["since"] = since.isoformat(timespec='seconds')

            while True:
                r = session.get(self._comments_url, params=query_params)
                r.raise_for_status()

                results: list[dict[str, Any]] = r.json()
                if not results:
                    # End of list
                    break

                for result in results:
                    yield Comment(result)
                query_params["page"] += 1


class Issue(_IssueOrPR):
    pass


class PR(_IssueOrPR):
    pass


def save_comment(comment: Comment, folder: Path) -> None:
    next_number = 1
    number = None

    for path in folder.iterdir():
        if not path.is_file():
            continue

        m = re.fullmatch(r"(\d+)_(.*)\.txt", path.name)
        if not m:
            continue

        # Use next sequential number
        next_number = max(int(m.group(1)) + 1, next_number)

        if m.group(2) == comment.author_username:
            with path.open("r", encoding="utf-8") as file:
                if file.readline() == f"GitHub ID: {comment.github_id}\n":
                    print(f"      Comment number {number} from {comment.author_username} has been edited, overwriting")
                    path.unlink()
                    number = int(m.group(1))
                    break

    if number is None:
        number = next_number
        print(f"      New comment number {number} from {comment.author_username}")

    file_path = folder / f"{number:04}_{comment.author_username}.txt"

    with file_path.open("w", encoding="utf-8") as file:
        file.write(f"GitHub ID: {comment.github_id}\n")
        file.write(f"Author: {comment.author_username}\n")
        file.write(f"Created: {comment.created.isoformat()}\n")
        file.write("\n")
        file.write(comment.text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="GitHub repository to back up (e.g. https://github.com/Akuli/porcupine)")
    parser.add_argument("dest", help="Folder where to back up the repository (e.g. ./issues)")
    parser.add_argument("--token", help="Github API token (optional, but specifying a token helps with rate limit issues)")
    args = parser.parse_args()

    m = re.fullmatch(r"(?:https://github.com/)?([^/]+)/([^/]+)/?", args.repo)
    if m is None:
        parser.error("repository must be given in https://github.com/user/repo format")
    repo = Repo(m.group(1), m.group(2))

    dest_folder = Path(args.dest)
    print(f"Backing up issue and PR comments: https://github.com/{repo.owner}/{repo.repo} --> {dest_folder}")
    dest_folder.mkdir(parents=True, exist_ok=True)

    if args.token is not None:
        set_token(args.token)

    start_time = datetime.now(timezone.utc)

    try:
        with (dest_folder / "info.txt").open("r") as file:
            line = file.readline()
            assert line.startswith("LastUpdated: ")
            since = datetime.fromisoformat(line.split(": ")[1].strip())
            since -= timedelta(minutes=10)  # in case clocks are out of sync
    except FileNotFoundError:
        since = None
    else:
        print(f"  Previous update on {since}. Updating only what has changed.")

    for issue_or_pr in repo.issues_and_prs(since):
        if isinstance(issue_or_pr, Issue):
            print(f"  Found issue #{issue_or_pr.number}: {issue_or_pr.title}")
            issue_or_pr_folder = dest_folder / f"issue_{issue_or_pr.number:05}"
        else:
            print(f"  Found PR #{issue_or_pr.number}: {issue_or_pr.title}")
            issue_or_pr_folder = dest_folder / f"pr_{issue_or_pr.number:05}"

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

        if issue_or_pr.updated == last_updated:
            print("    Already up to date")
            continue

        for comment in issue_or_pr.iter_comments(since):
            print(f"    Found comment from {comment.author_username}")
            save_comment(comment, issue_or_pr_folder)

        # Write info after all comments, so that the issue or pull request
        # is not considered to be up-to-date if something errors
        with (issue_or_pr_folder / "info.txt").open("w") as file:
            file.write(f"Title: {issue_or_pr.title}\n")
            file.write(f"Updated: {issue_or_pr.updated.isoformat()}\n")

    with (dest_folder / "info.txt").open("w") as file:
        file.write(f"LastUpdated: {start_time}\n")


main()

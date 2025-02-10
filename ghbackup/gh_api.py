from __future__ import annotations
import requests
from typing import Any, cast
from datetime import datetime, timezone
from collections.abc import Iterator


session = requests.Session()

# These are optional, but GitHub recommends setting them
session.headers["Accept"] = "application/vnd.github+json"
session.headers["X-GitHub-Api-Version"] = "2022-11-28"


def set_token(token: str) -> None:
    """Authenticate all future requests with given token to prevent rate limit issues"""
    session.headers["Authorization"] = f"Token {token}"


class Repo:
    def __init__(self, owner_and_repo: str) -> None:
        # e.g. Akuli/porcupine
        self.owner, self.repo = owner_and_repo.split("/")

    def issues_and_prs(self, since: datetime | None) -> Iterator[Issue | PR]:
        query_params: dict[str, Any] = {
            "state": "all",  # open and closed
            "page": 1,
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
        self.text: str = github_json["body"]
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

        self._comments_url = github_json["comments_url"]

        # The JSON has same fields that comments have
        self._initial_comment = Comment(github_json)
        self.title: str = github_json["title"]
        self.number: int = github_json["number"]

        # The "created_at" field is in the initial comment
        self.updated = datetime.fromisoformat(github_json["updated_at"])

    def __repr__(self) -> str:
        # Example: <issue #123>
        return f"<{type(self).__name__} #{self.number}>"

    def iter_comments(self, since: datetime | None) -> Iterator[Comment]:
        yield self._initial_comment

        query_params: dict[str, Any] = {"page": 1}
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

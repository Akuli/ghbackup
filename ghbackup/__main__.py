import argparse
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from .gh_api import Repo, Issue, Comment, set_token, PR


repos = [
    Repo("Akuli/jou"),
]


def save_comment(comment: Comment, folder: Path) -> None:
    file_path = None
    next_number = 1

    for path in folder.iterdir():
        if not path.is_file():
            continue

        m = re.fullmatch(r"(\d+)_(.*)\.txt", path.name)
        if not m:
            continue

        next_number = max(int(m.group(1)) + 1, next_number)
        if m.group(2) == comment.author_username:
            with path.open("r", encoding="utf-8") as file:
                if file.readline() == f"GitHub ID: {comment.github_id}\n":
                    # Overwrite this file
                    file_path = path
                    break

    if file_path is None:
        # New comment, do not overwrite, use next sequential number
        file_path = folder / f"{next_number:04}_{comment.author_username}.txt"

    with file_path.open("w", encoding="utf-8") as file:
        file.write(f"GitHub ID: {comment.github_id}\n")
        file.write(f"Author: {comment.author_username}\n")
        file.write(f"Created: {comment.created.isoformat()}\n")
        file.write("\n")
        file.write(comment.text)


def determine_issue_or_pr_folder(parent_folder: Path, issue_or_pr: Issue | PR) -> Path:
    if isinstance(issue_or_pr, Issue):
        prefix = "issue"
    else:
        prefix = "pr"

    sanitized_title = re.sub(r"[^A-Za-z0-9-_]", "_", issue_or_pr.title)
    result = parent_folder / f"{prefix}_{issue_or_pr.number}_{sanitized_title}"

    for existing in parent_folder.iterdir():
        if existing.is_dir() and existing.name.startswith(f"{prefix}_{issue_or_pr.number}_"):
            # Exists, but with wrong name. Happens when title is changed.
            existing.rename(result)
            break

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="GitHub repository to back up in user/repo format (e.g. Akuli/porcupine)")
    parser.add_argument("dest", help="Folder where to back up the repository (e.g. ./issues)")
    parser.add_argument("--token", help="Github API token (optional, but specifying a token helps with rate limit issues)")
    args = parser.parse_args()

    if args.token is not None:
        set_token(args.token)

    for repo in repos:
        # TODO: try to read last_updated.txt or something like that
        since = datetime.now(timezone.utc) - timedelta(days=1)

        repo_folder = Path(repo.repo)
        print(f"Backing up comments: https://github.com/{repo.owner}/{repo.repo} --> {repo_folder}")
        repo_folder.mkdir(exist_ok=True)

        for issue_or_pr in repo.issues_and_prs(since):
            if isinstance(issue_or_pr, Issue):
                print(f"  Found issue #{issue_or_pr.number}: {issue_or_pr.title}")
            else:
                print(f"  Found PR #{issue_or_pr.number}: {issue_or_pr.title}")

            issue_or_pr_folder = determine_issue_or_pr_folder(repo_folder, issue_or_pr)
            issue_or_pr_folder.mkdir(exist_ok=True)

            for comment in issue_or_pr.iter_comments(since):
                print(f"    Found comment from {comment.author_username}")
                save_comment(comment, issue_or_pr_folder)

            # Write info after all comments, so that the issue or pull request
            # is not considered to be up-to-date if something errors
            with (issue_or_pr_folder / "info.txt").open("w") as file:
                file.write(f"Title: {issue_or_pr.title}\n")
                file.write(f"Updated: {issue_or_pr.updated.isoformat()}\n")


main()

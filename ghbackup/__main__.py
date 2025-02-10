import argparse
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

from .gh_api import Repo, Issue, Comment, set_token, PR


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
    parser.add_argument("repo", help="GitHub repository to back up (e.g. https://github.com/Akuli/porcupine)")
    parser.add_argument("dest", type=Path, help="Folder where to back up the repository (e.g. ./issues)")
    parser.add_argument("--token", help="Github API token (optional, but specifying a token helps with rate limit issues)")
    args = parser.parse_args()

    dest_folder: Path = args.dest

    m = re.fullmatch(r"(?:https://github.com/)?([^/]+)/([^/]+)/?", args.repo)
    if m is None:
        parser.error("repository must be given in https://github.com/user/repo format")
    repo = Repo(m.group(1), m.group(2))

    if args.token is not None:
        set_token(args.token)

    dest_folder.mkdir(parents=True, exist_ok=True)

    start_time = datetime.now(timezone.utc)

    try:
        with (dest_folder / "info.txt").open("r") as file:
            line = file.readline()
            assert line.startswith("LastUpdated: ")
            since = datetime.fromisoformat(line.split(": ")[1].strip())
            since -= timedelta(minutes=10)  # in case clocks are out of sync
    except FileNotFoundError:
        since = None

    repo_folder = args.dest
    print(f"Backing up comments: https://github.com/{repo.owner}/{repo.repo} --> {repo_folder}")
    repo_folder.mkdir(exist_ok=True)

    for issue_or_pr in repo.issues_and_prs(since):
        if isinstance(issue_or_pr, Issue):
            print(f"  Found issue #{issue_or_pr.number}: {issue_or_pr.title}")
        else:
            print(f"  Found PR #{issue_or_pr.number}: {issue_or_pr.title}")

        issue_or_pr_folder = determine_issue_or_pr_folder(repo_folder, issue_or_pr)
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

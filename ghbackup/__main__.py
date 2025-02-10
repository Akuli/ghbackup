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
    number = 1

    for path in folder.iterdir():
        if not path.is_file():
            continue

        m = re.match('(\d+)_.*\.txt', path.name)
        if m is None:
            continue
        number = max(m.group(0) + 1, number)

        comment_count += 1
        with item.open("r", encoding="utf-8") as file:
            if file.readline() == f"GitHub ID: {comment.github_id}\n":
                # Overwrite this file
                file_path = path
                break

    if file_path is None:
        # New comment, do not overwrite, use next sequential number
        file_path = folder / f"{number}_{comment.author_username}.txt"

    with file_path.open("w", encoding="utf-8") as file:
        file.write(f"GitHub ID: {comment.github_id}\n")
        file.write(f"Author: {comment.author_username}\n")
        file.write(f"Created: {comment.created.isoformat()}\n")
        file.write("\n")
        file.write(comment.text)


def determine_issue_or_pr_folder(parent_folder: Path, issue_or_pr: Issue | PR) -> str:
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
    parser.add_argument('--token', help="Github API token (optional, but specifying a token helps with rate limit issues)")
    args = parser.parse_args()

    if args.token is not None:
        set_token(args.token)

    for repo in repos:
        # TODO: try to read last_updated.txt or something like that
        since = datetime.now(timezone.utc) - timedelta(days=1)

        repo_folder = Path(repo.repo)
        print(f"Backing up comments: https://github.com/{repo.owner}/{repo.repo} --> to ./{repo_folder}")

        for issue_or_pr in repo.issues_and_prs(since):
            if isinstance(issue_or_pr, Issue):
                what_is_it_short = "issue"
                what_is_it_long = "issue"
            else:
                what_is_it_short = "pull request"
                what_is_it_long = "pr"
            print(f"  Found {what_is_it_long} #{issue_or_pr.number}: {issue_or_pr.title}")

            issue_or_pr_folder = repo_folder / f"{what_is_it_short}_{issue_or_pr.number}_{sanitize()}"
            issue_or_pr_folder.mkdir(parents=True, exist_ok=True)

            for comment in issue_or_pr.iter_comments(since):
                print(f"    Found comment from {comment.author_username}")
                save_comment(comment, issue_or_pr_folder)

            # Write info after all comments, so that the issue or pull request
            # is not considered to be up-to-date if something errors
            file_headers = {
                "Title": issue_or_pr.title,
                "Updated": issue_or_pr.updated,
            }
            (issue_or_pr_folder / "info.txt").write_text(format_headers(file_headers))


main()

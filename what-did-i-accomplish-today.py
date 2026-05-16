#!/usr/bin/env python3
"""Review today's git commits from GitHub and Gitea and write a markdown summary."""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
import urllib.parse
from datetime import date, timedelta, datetime, timezone

GITHUB_USER = os.environ.get("GITHUB_USER", "kevinpinscoe")
GITEA_HOST = "https://git.kevininscoe.com"
GITEA_USER = "kinscoe"
GITEA_AUTHOR_EMAIL = "kevin.inscoe@gmail.com"
GITEA_TOKEN_FILE = os.path.expanduser("~/.config/gitea/api")
JOURNAL_ROOT = os.path.expanduser("~/Journal/Personal Journal")
OUTPUT_SUBDIR = "ACCOMPLISHMENTS"


def today_bounds():
    today = date.today()
    since = f"{today.isoformat()}T00:00:00Z"
    until = f"{(today + timedelta(days=1)).isoformat()}T00:00:00Z"
    return today, since, until


def run_gh(path, jq_filter=None):
    cmd = ["gh", "api", path]
    if jq_filter:
        cmd += ["--jq", jq_filter]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def gitea_get(path, token, params=None):
    url = f"{GITEA_HOST}/api/v1{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def get_github_commits(since, until):
    """Find today's commits on GitHub via the Events API + per-repo commits API."""
    today_prefix = since[:10]
    repos_today = set()

    for page in range(1, 11):
        events = run_gh(f"/users/{GITHUB_USER}/events?per_page=100&page={page}")
        if not events:
            break
        oldest = None
        for ev in events:
            created = ev.get("created_at", "")
            if oldest is None or created < oldest:
                oldest = created
            if ev.get("type") == "PushEvent" and created.startswith(today_prefix):
                repos_today.add(ev["repo"]["name"])
        if oldest and oldest[:10] < today_prefix:
            break

    jq = '[.[] | {sha: .sha[:7], message: (.commit.message | split("\\n")[0]), date: .commit.committer.date, author: .commit.author.email}]'
    commits_by_repo = {}
    for repo in sorted(repos_today):
        path = f"/repos/{repo}/commits?since={since}&until={until}&author={GITHUB_USER}&per_page=100"
        data = run_gh(path, jq_filter=jq)
        if data:
            commits_by_repo[repo] = data
    return commits_by_repo


def get_gitea_commits(token, since, until):
    """Find today's commits on Gitea by checking repos updated today."""
    today_prefix = since[:10]
    all_repos = []
    page = 1
    while True:
        data = gitea_get("/repos/search", token, {"limit": 50, "page": page})
        if not data:
            break
        batch = data.get("data", [])
        if not batch:
            break
        all_repos.extend(batch)
        if len(batch) < 50:
            break
        page += 1

    repos_today = [
        r["full_name"]
        for r in all_repos
        if r.get("updated_at", "")[:10] >= today_prefix
    ]

    commits_by_repo = {}
    for full_name in sorted(repos_today):
        owner, repo = full_name.split("/", 1)
        data = gitea_get(
            f"/repos/{owner}/{repo}/commits",
            token,
            {"since": since, "until": until, "limit": 50},
        )
        if not isinstance(data, list):
            continue
        matching = []
        for c in data:
            commit_block = c.get("commit", {})
            author = commit_block.get("author", {})
            committer = commit_block.get("committer", {})
            if author.get("email") == GITEA_AUTHOR_EMAIL or committer.get("email") == GITEA_AUTHOR_EMAIL:
                sha = c.get("sha", "")[:7]
                message = commit_block.get("message", "").split("\n")[0]
                commit_date = author.get("date", "")
                matching.append({"sha": sha, "message": message, "date": commit_date})
        if matching:
            commits_by_repo[full_name] = matching


    return commits_by_repo


def format_date(raw):
    """Format an ISO date string to YYYY-MM-DD HH:MM local time."""
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        local = dt.astimezone()
        return local.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return raw[:16]


def build_markdown(today, github_commits, gitea_commits):
    lines = [
        f"# What did I accomplish today",
        f"",
        f"Date: {today.isoformat()}",
        f"",
        f"## Commits",
        f"",
    ]

    lines.append("### GitHub\n")
    if github_commits:
        for repo, commits in sorted(github_commits.items()):
            lines.append(f"#### {repo}\n")
            for c in commits:
                lines.append(f"- `{c['sha']}` {c['message']} ({format_date(c['date'])})")
            lines.append("")
    else:
        lines.append("*(no commits today)*\n")

    lines.append(f"### Gitea ({GITEA_HOST.replace('https://', '')})\n")
    if gitea_commits:
        for repo, commits in sorted(gitea_commits.items()):
            lines.append(f"#### {repo}\n")
            for c in commits:
                lines.append(f"- `{c['sha']}` {c['message']} ({format_date(c['date'])})")
            lines.append("")
    else:
        lines.append("*(no commits today)*\n")

    return "\n".join(lines)


def write_output(today, content):
    date_str = today.isoformat()
    out_dir = os.path.join(JOURNAL_ROOT, OUTPUT_SUBDIR, date_str)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"git-work-for-{date_str}.md")
    with open(out_path, "w") as f:
        f.write(content + "\n")
    return out_path


def main():
    today, since, until = today_bounds()

    print(f"Fetching GitHub commits for {today.isoformat()}...", file=sys.stderr)
    github_commits = get_github_commits(since, until)

    token = None
    token_path = os.path.expanduser(GITEA_TOKEN_FILE)
    if os.path.exists(token_path):
        token = open(token_path).read().strip()

    gitea_commits = {}
    if token:
        print(f"Fetching Gitea commits for {today.isoformat()}...", file=sys.stderr)
        gitea_commits = get_gitea_commits(token, since, until)
    else:
        print(f"Warning: Gitea token not found at {GITEA_TOKEN_FILE}", file=sys.stderr)

    content = build_markdown(today, github_commits, gitea_commits)

    out_path = write_output(today, content)
    print(f"\nWritten to: {out_path}\n", file=sys.stderr)
    print(content)


if __name__ == "__main__":
    main()

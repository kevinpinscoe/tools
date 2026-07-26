#!/usr/bin/env python3
"""Review today's git commits from GitHub and Gitea and write a markdown summary."""

import json
import os
import shutil
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
# On-disk ~/.config/gitea/api was shredded 2026-07-12 when Gitea credentials
# moved to OpenBao (mount=app, path=gitea) — see ~/.secrets/CREDENTIAL-MAP.md.
# Fall back to on-disk only if still present; OpenBao is the source of truth.
GITEA_TOKEN_FILE = os.path.expanduser("~/.config/gitea/api")
BAO_ADDR = "https://openbao.kevininscoe.com"
VAULT_TOKEN_FILE = os.path.expanduser("~/.environment/.vault-token")
# systemd's minimal PATH excludes ~/.local/bin, where bao is installed, so a bare
# "bao" resolves interactively but not under the timer. Resolve it explicitly.
BAO_BIN = (
    os.environ.get("BAO_BIN")
    or shutil.which("bao")
    or os.path.expanduser("~/.local/bin/bao")
)
_journal_env = os.environ.get("JOURNAL_PATH", "")
if not _journal_env:
    raise SystemExit("what-did-i: JOURNAL_PATH env var not set — invoke via the 'what-did-i' wrapper")
JOURNAL_ROOT = os.path.expanduser(_journal_env)
OUTPUT_SUBDIR = "ACCOMPLISHMENTS"
# Run marker consumed by ~/admin/check-what-did-i/. Records whether each forge was
# actually reachable, so a degraded GitHub-only run is distinguishable from a
# genuinely quiet day — a commit count of zero cannot tell those apart.
RUN_MARKER = os.path.expanduser("~/.local/state/what-did-i-last-run.json")


def date_bounds(target: date):
    since = f"{target.isoformat()}T00:00:00Z"
    until = f"{(target + timedelta(days=1)).isoformat()}T00:00:00Z"
    return since, until


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

    # Page until the feed is exhausted. GitHub caps this resource at 300 events
    # (it returns HTTP 422 from page 4), so this is at most three calls.
    #
    # Do NOT early-exit on "this page's oldest event predates the target". The
    # feed is not strictly ordered — a single stray old event on page 1 (there is
    # one from 2026-05-05) ended the loop immediately, so any day whose events had
    # scrolled onto page 2+ silently reported zero GitHub commits.
    for page in range(1, 11):
        events = run_gh(f"/users/{GITHUB_USER}/events?per_page=100&page={page}")
        if not events:
            break
        for ev in events:
            created = ev.get("created_at", "")
            if ev.get("type") == "PushEvent" and created.startswith(today_prefix):
                repos_today.add(ev["repo"]["name"])

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


def get_gitea_token():
    """Resolve the Gitea API token: on-disk file first, else OpenBao (app/gitea)."""
    if os.path.exists(GITEA_TOKEN_FILE):
        token = open(GITEA_TOKEN_FILE).read().strip()
        if token:
            return token

    vault_token_path = VAULT_TOKEN_FILE
    if not os.path.exists(vault_token_path):
        return None
    vault_token = open(vault_token_path).read().strip()
    if not vault_token:
        return None

    env = {**os.environ, "BAO_ADDR": BAO_ADDR, "BAO_TOKEN": vault_token}
    # Degrade to a GitHub-only report rather than aborting: a missing or broken bao
    # must not cost us the GitHub commits already fetched.
    try:
        result = subprocess.run(
            [BAO_BIN, "kv", "get", "-field=token", "-mount=app", "gitea"],
            capture_output=True, text=True, env=env,
        )
    except OSError as exc:
        print(f"Warning: could not run '{BAO_BIN}': {exc}", file=sys.stderr)
        return None
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


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


def build_markdown(target: date, github_commits, gitea_commits):
    label = "today" if target == date.today() else target.isoformat()
    lines = [
        "---",
        "tags:",
        "  - accomplishments",
        "action: generated",
        "---",
        "",
        f"# What did I accomplish {label}",
        f"",
        f"Date: {target.isoformat()}",
        f"",
        f"## Commits",
        f"",
    ]

    no_commits = f"*(no commits {label})*\n"

    lines.append("### GitHub\n")
    if github_commits:
        for repo, commits in sorted(github_commits.items()):
            lines.append(f"#### {repo}\n")
            for c in commits:
                lines.append(f"- `{c['sha']}` {c['message']} ({format_date(c['date'])})")
            lines.append("")
    else:
        lines.append(no_commits)

    lines.append(f"### Gitea ({GITEA_HOST.replace('https://', '')})\n")
    if gitea_commits:
        for repo, commits in sorted(gitea_commits.items()):
            lines.append(f"#### {repo}\n")
            for c in commits:
                lines.append(f"- `{c['sha']}` {c['message']} ({format_date(c['date'])})")
            lines.append("")
    else:
        lines.append(no_commits)

    return "\n".join(lines)


def write_output(target: date, content):
    date_str = target.isoformat()
    month_str = target.strftime("%Y-%m")
    out_dir = os.path.join(JOURNAL_ROOT, OUTPUT_SUBDIR, month_str)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"git-work-for-{date_str}.md")
    with open(out_path, "w") as f:
        f.write(content + "\n")
    return out_path


USAGE = "Usage: what-did-i [yesterday | YYYY-MM-DD] [-h|--help]"
KNOWN_ARGS = {"-h", "--help", "yesterday"}


def parse_iso_date(arg):
    """Return the date for a YYYY-MM-DD argument, or None if it isn't one."""
    try:
        return date.fromisoformat(arg)
    except ValueError:
        return None


def write_run_marker(target: date, out_path, github_ok, gitea_ok,
                     github_commits, gitea_commits):
    """Record the outcome of this run for the monitoring check to assert against."""
    marker = {
        "date": target.isoformat(),
        "output_file": out_path,
        "output_bytes": os.path.getsize(out_path) if os.path.exists(out_path) else 0,
        "github_ok": github_ok,
        "gitea_ok": gitea_ok,
        "github_commits": sum(len(v) for v in github_commits.values()),
        "gitea_commits": sum(len(v) for v in gitea_commits.values()),
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(RUN_MARKER), exist_ok=True)
    with open(RUN_MARKER, "w") as fh:
        json.dump(marker, fh, indent=2)


def main():
    unknown = [
        a for a in sys.argv[1:]
        if a.lower() not in KNOWN_ARGS and parse_iso_date(a) is None
    ]
    if unknown:
        print(f"what-did-i: unrecognised argument(s): {' '.join(unknown)}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    if any(a in {"-h", "--help"} for a in sys.argv[1:]):
        print(USAGE)
        sys.exit(0)

    explicit = next(
        (d for d in (parse_iso_date(a) for a in sys.argv[1:]) if d is not None), None
    )
    use_yesterday = any(a.lower() == "yesterday" for a in sys.argv[1:])
    if explicit is not None:
        target = explicit
    elif use_yesterday:
        target = date.today() - timedelta(days=1)
    else:
        target = date.today()
    since, until = date_bounds(target)

    print(f"Fetching GitHub commits for {target.isoformat()}...", file=sys.stderr)
    github_commits = get_github_commits(since, until)

    token = get_gitea_token()

    gitea_commits = {}
    if token:
        print(f"Fetching Gitea commits for {target.isoformat()}...", file=sys.stderr)
        gitea_commits = get_gitea_commits(token, since, until)
    else:
        print(
            f"Warning: Gitea token not found (checked {GITEA_TOKEN_FILE} and OpenBao app/gitea)",
            file=sys.stderr,
        )

    content = build_markdown(target, github_commits, gitea_commits)

    out_path = write_output(target, content)

    # Reachability probes, not commit counts: an empty report is ambiguous on its
    # own — a quiet day and a broken credential both produce zero commits.
    github_ok = run_gh("/user") is not None
    gitea_ok = bool(token) and gitea_get("/user", token) is not None
    write_run_marker(target, out_path, github_ok, gitea_ok,
                     github_commits, gitea_commits)

    print(f"\nWritten to: {out_path}\n", file=sys.stderr)
    print(content)


if __name__ == "__main__":
    main()

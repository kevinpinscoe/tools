#!/usr/bin/env python3
"""
Interactively create a new YouTrack issue in either "Work - Inbox" or
"Kevin - Inbox", populating the Description body and the "Ticket link"
custom field. Status/Priority/Date time entered use project defaults.

Credentials: ~/.config/YouTrack/self-host-api.txt
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import request, parse, error

_youtrack_server = os.environ.get("YOUTRACK_SERVER", "")
if not _youtrack_server:
    print("ERROR: YOUTRACK_SERVER is not set; source ~/.environment/self-hosted-services.sh", file=sys.stderr)
    sys.exit(1)
YOUTRACK_BASE_URL = _youtrack_server.rstrip("/")

YOUTRACK_TOKEN_FILE = Path.home() / ".config/YouTrack/self-host-api.txt"

WORK_INBOX_NAME = "Work - Inbox"
KEVIN_INBOX_NAME = "Kevin - Inbox"
FIELD_TICKET_LINK_NAME = "Ticket link"


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_token(path: Path) -> str:
    if not path.is_file():
        die(f"YouTrack token file not found: {path}")
    if not os.access(path, os.R_OK):
        die(f"YouTrack token file not readable: {path} (try: chmod 600 {path})")
    return path.read_text().strip()


def http_request(method: str, url: str, headers: dict, body: dict | None = None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = e.code
    try:
        return status, json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return status, raw


def find_project_id(yt_headers: dict, name: str) -> str:
    params = parse.urlencode({"fields": "id,name,shortName"})
    status, body = http_request(
        "GET", f"{YOUTRACK_BASE_URL}/api/admin/projects?{params}", yt_headers
    )
    if status != 200 or not isinstance(body, list):
        die(f"Failed to list projects (HTTP {status}): {body}")
    for proj in body:
        if proj.get("name") == name:
            return proj["id"]
    die(f"Project not found: {name!r}")


def find_ticket_link_field_id(yt_headers: dict, project_id: str) -> str:
    params = parse.urlencode({"fields": "id,field(name)"})
    url = f"{YOUTRACK_BASE_URL}/api/admin/projects/{project_id}/customFields?{params}"
    status, body = http_request("GET", url, yt_headers)
    if status != 200 or not isinstance(body, list):
        die(f"Failed to list project custom fields (HTTP {status}): {body}")
    for cf in body:
        if (cf.get("field") or {}).get("name") == FIELD_TICKET_LINK_NAME:
            return cf["id"]
    die(f"Custom field {FIELD_TICKET_LINK_NAME!r} not found on project {project_id}")


def prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    suffix = "Y/n" if default_yes else "y/N"
    while True:
        ans = input(f"{question} ({suffix}): ").strip().lower()
        if not ans:
            return default_yes
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Please answer y or n.")


def prompt_required(label: str) -> str:
    while True:
        val = input(f"{label}: ").strip()
        if val:
            return val
        print(f"  {label} cannot be blank.")


def create_issue(yt_headers: dict, project_id: str, summary: str, description: str) -> tuple[str, str]:
    url = f"{YOUTRACK_BASE_URL}/api/issues?fields=id,idReadable"
    body = {
        "project": {"id": project_id},
        "summary": summary,
        "description": description,
    }
    status, resp = http_request("POST", url, yt_headers, body)
    if status not in (200, 201) or not isinstance(resp, dict):
        die(f"Create issue failed (HTTP {status}): {resp}")
    return resp["id"], resp.get("idReadable") or resp["id"]


def set_simple_field(yt_headers: dict, issue_id: str, field_id: str, value: str) -> None:
    url = f"{YOUTRACK_BASE_URL}/api/issues/{issue_id}/fields/{field_id}?fields=name,value"
    status, resp = http_request("POST", url, yt_headers, {"value": value})
    if status not in (200, 201):
        raise RuntimeError(f"set field {field_id} HTTP {status}: {resp}")


def main() -> int:
    yt_token = load_token(YOUTRACK_TOKEN_FILE)
    yt_headers = {
        "Authorization": f"Bearer {yt_token}",
        "Accept": "application/json",
    }

    is_work = prompt_yes_no("Is this work", default_yes=True)
    project_name = WORK_INBOX_NAME if is_work else KEVIN_INBOX_NAME

    description = prompt_required("Description")
    ticket_link = input("Ticket link (optional): ").strip()

    summary = description.splitlines()[0].strip()
    if len(summary) > 120:
        summary = summary[:117] + "..."

    print(f">>> Resolving project {project_name!r}…")
    project_id = find_project_id(yt_headers, project_name)

    print(">>> Creating issue…")
    issue_id, issue_readable = create_issue(yt_headers, project_id, summary, description)

    if ticket_link:
        try:
            field_id = find_ticket_link_field_id(yt_headers, project_id)
            set_simple_field(yt_headers, issue_id, field_id, ticket_link)
        except Exception as e:
            print(f"WARN: failed to set 'Ticket link': {e}")

    issue_url = f"{YOUTRACK_BASE_URL}/issue/{issue_readable}"
    print(f"CREATED: {issue_readable} in {project_name}")
    print(f"URL: {issue_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

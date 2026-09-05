#!/usr/bin/env python3
"""
Interactively create a new YouTrack issue in either "Work" or "Kevin",
populating the Description body and the "Ticket link" custom field.
Type=Task, Category=INBOX, Status=To do, Issue domain, Assignee, and Date
time entered=now are all set explicitly. Status has no default in the
post-2026-07-29-rebuild schema and rejects the create with HTTP 400 if
omitted; Date time entered used to be auto-populated by a workflow that was
not recreated in the rebuilt instance, so it's set here instead. Priority
uses the project default.

Issue domain comes from the "Is this work" answer that already chooses the
project -- see ISSUE_DOMAIN_BY_WORK. Nothing here is inferred from the
description or the ticket link.

Assignee is always Kevin Inscoe (YouTrack login "admin"), in both projects
and regardless of the work/personal answer -- AI-26.

Credentials: OpenBao app/youtrack/work (field: token), mirrored on both the
mac-local and home (openbao.kevininscoe.com) instances as of 2026-08-12.
Read via bao_env_for_host(), which selects the mac-local instance on Work
hosts (work-macbook, mac-container) and the home instance on every other
host (FLDW, RPi5 "core", and any other Home host), per the host registry in
~/ai/directives/kevins-federated-unix-universe.md. This is the same pattern
used by the sibling
~/Projects/private/vanco-skills/skills/youtrack-get-my-assigned-tickets-from-jira-into-youtrack/get-my-assigned-tickets-from-jira-into-youtrack.py.
The old home-instance app/YouTrack token was invalidated by the 2026-07-29
rebuild (INC-2026-001); app/youtrack/work is the live credential on both
instances now.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from urllib import request, parse, error

_youtrack_server = os.environ.get("YOUTRACK_SERVER", "")
if not _youtrack_server:
    print("ERROR: YOUTRACK_SERVER is not set; source ~/.environment/self-hosted-services.sh", file=sys.stderr)
    sys.exit(1)
YOUTRACK_BASE_URL = _youtrack_server.rstrip("/")

WORK_INBOX_NAME = "Work"   # was "Work - Inbox" before the 2026-07-29 rebuild
KEVIN_INBOX_NAME = "Kevin"  # was "Kevin - Inbox" before the 2026-07-29 rebuild

# Custom fields are addressed by prototype ID, never by display name, per
# ~/ai/directives/when-creating-a-youtrack-ticket.md and
# youtrack.kevininscoe.com's reference/custom-fields.md -- this instance has
# historically carried duplicate-named prototypes (e.g. the unattached
# `State` 157-33 alongside the real `Status` 157-2). The REST API itself
# still addresses a field by name on the wire, so these IDs are resolved to
# their live display name via find_project_custom_fields() before use, never
# hardcoded as a guessed name.
FIELD_TYPE = "157-1"
FIELD_STATUS = "157-2"
FIELD_ASSIGNEE = "157-3"
FIELD_CATEGORY = "157-11"
FIELD_DATE_TIME_ENTERED = "157-15"
FIELD_ISSUE_DOMAIN = "157-30"
FIELD_TICKET_LINK = "157-27"

# Every issue this script creates is assigned to Kevin Inscoe, regardless of
# which project/domain the "Is this work" answer routes it to -- his YouTrack
# login is "admin" (see `~/ai/directives/when-creating-a-youtrack-ticket.md`
# Sec. 6: this script isn't the AI filing the issue on its own initiative, so
# the Claude_Code-assignee convention there doesn't apply here).
ASSIGNEE_LOGIN = "admin"

# "Issue domain" (prototype 157-30) is a single-value enum shared by every project. Its
# bundle offers Personal / Employer work / Client work -- there is no value named "Work",
# because "work" alone does not separate employer work from contracted client work.
#
# The domain is not asked separately: the "Is this work" prompt below already answers it,
# and asking the same question twice in a row invites the two answers to disagree. Client
# work has no prompt here -- set it in the web UI on the rare issue that needs it.
ISSUE_DOMAIN_BY_WORK = {True: "Employer work", False: "Personal"}


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _is_work_host(host: str) -> bool:
    """True if `host` is (or -- for an unnamed host -- resolves via the generic
    fallback signals to) a Work-category host, per
    ~/ai/directives/kevins-federated-unix-universe.md."""
    if host in ("KevinI-MBP24", "b38e685e79b8"):
        return True
    if host in ("kevin", "core"):
        return False
    # Unnamed host: fall back to the generic signals from root-directive.md.
    return platform.system() == "Darwin" or os.path.isdir("/mac-home")


def bao_env_for_host(mount_hint: str) -> dict:
    """Build the environment for a `bao` CLI call, selecting the correct
    OpenBao instance for the current host.

    app/youtrack/work is mirrored on two instances (see module docstring):

      - work-macbook (hostname KevinI-MBP24): the mac-local instance *is*
        127.0.0.1:8200 on this host. The Mac's shell init exports the
        home-instance BAO_TOKEN, which shadows the mac-local login and causes
        a false "permission denied" here -- strip it so the bao CLI falls
        back to its own cached mac-local session token.
      - mac-container (hostname b38e685e79b8): 127.0.0.1 is the container's
        own loopback, not the Mac's. Docker Desktop's host-alias
        host.docker.internal:8200 reaches the same mac-local instance
        instead. Unlike work-macbook, this container's BAO_TOKEN env var is
        already the valid credential for that instance -- keep it, don't
        strip it.
      - any other, unnamed Work host: mac-local OpenBao's address is unknown
        for it. Fail clearly rather than guessing.

    Every other host (FLDW, RPi5 "core", and any other Home host) reaches the
    home instance (openbao.kevininscoe.com) using the on-disk session token,
    per ~/ai/directives/storing-secrets.md. `mount_hint` is used only to make
    the error message name the path that failed to resolve.
    """
    host = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    env = dict(os.environ)
    if host == "KevinI-MBP24":
        env.pop("BAO_TOKEN", None)
        env["BAO_ADDR"] = "http://127.0.0.1:8200"
    elif host == "b38e685e79b8":
        env["BAO_ADDR"] = "http://host.docker.internal:8200"
    elif _is_work_host(host):
        die(
            f"Unrecognized host '{host}' -- it matches the Work fallback signals "
            f"but mac-local OpenBao ({mount_hint})'s address is unknown for it. "
            "Add this host to ~/ai/directives/kevins-federated-unix-universe.md "
            "if it's a new, legitimate Work host."
        )
    else:
        env["BAO_ADDR"] = "https://openbao.kevininscoe.com"
        token_path = os.path.expanduser("~/.environment/.vault-token")
        try:
            with open(token_path) as f:
                env["BAO_TOKEN"] = f.read().strip()
        except OSError as e:
            die(f"Failed to read home OpenBao session token at {token_path}: {e}")
    return env


def load_youtrack_token() -> str:
    """Retrieve the YouTrack API token from OpenBao (app/youtrack/work),
    instance chosen by host -- see bao_env_for_host()."""
    env = bao_env_for_host("app/youtrack/work")
    result = subprocess.run(
        ["bao", "kv", "get", "-field=token", "-mount=app", "youtrack/work"],
        env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        die(f"Failed to retrieve YouTrack token from OpenBao: {result.stderr.strip()}")
    return result.stdout.strip()


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


def find_project_custom_fields(yt_headers: dict, project_id: str) -> dict[str, dict]:
    """Map each attached field's prototype ID to its live display name and
    per-project attachment ID, keyed by prototype ID (e.g. "157-2") so every
    other function resolves a field by ID and never by a guessed name."""
    params = parse.urlencode({"fields": "id,field(id,name)", "$top": "100"})
    url = f"{YOUTRACK_BASE_URL}/api/admin/projects/{project_id}/customFields?{params}"
    status, body = http_request("GET", url, yt_headers)
    if status != 200 or not isinstance(body, list):
        die(f"Failed to list project custom fields (HTTP {status}): {body}")
    by_proto: dict[str, dict] = {}
    for cf in body:
        field = cf.get("field") or {}
        proto_id = field.get("id")
        if proto_id:
            by_proto[proto_id] = {"attachment_id": cf["id"], "name": field.get("name")}
    return by_proto


def resolve_field(by_proto: dict[str, dict], proto_id: str, project_id: str) -> dict:
    entry = by_proto.get(proto_id)
    if entry is None:
        die(f"Custom field prototype {proto_id!r} not attached to project {project_id}")
    return entry


def find_user_id(yt_headers: dict, login: str) -> str:
    params = parse.urlencode({"fields": "id,login,fullName", "$top": "1000"})
    status, body = http_request(
        "GET", f"{YOUTRACK_BASE_URL}/api/users?{params}", yt_headers
    )
    if status != 200 or not isinstance(body, list):
        die(f"Failed to list users (HTTP {status}): {body}")
    for user in body:
        if user.get("login") == login:
            return user["id"]
    die(f"YouTrack user not found: {login!r}")


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


def create_issue(yt_headers: dict, project_id: str, summary: str, description: str,
                 issue_domain: str, assignee_id: str, by_proto: dict[str, dict]) -> tuple[str, str]:
    # POST /api/issues addresses a field by name on the wire, not by
    # projectCustomField id -- sending the id there is rejected with the same
    # opaque 400 as a wrong $type. So the name is resolved from the prototype
    # ID here and only the resolved name goes in the payload.
    def name(proto_id: str) -> str:
        return resolve_field(by_proto, proto_id, project_id)["name"]

    url = f"{YOUTRACK_BASE_URL}/api/issues?fields=id,idReadable"
    body = {
        "project": {"id": project_id},
        "summary": summary,
        "description": description,
        "customFields": [
            {"name": name(FIELD_TYPE), "$type": "SingleEnumIssueCustomField", "value": {"name": "Task"}},
            {"name": name(FIELD_CATEGORY), "$type": "StateIssueCustomField", "value": {"name": "INBOX"}},
            {"name": name(FIELD_STATUS), "$type": "StateIssueCustomField", "value": {"name": "To do"}},
            {"name": name(FIELD_ISSUE_DOMAIN), "$type": "SingleEnumIssueCustomField", "value": {"name": issue_domain}},
            {"name": name(FIELD_ASSIGNEE), "$type": "SingleUserIssueCustomField",
             "value": {"id": assignee_id, "$type": "User"}},
            {"name": name(FIELD_DATE_TIME_ENTERED), "$type": "SimpleIssueCustomField", "value": int(time.time() * 1000)},
        ],
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
    yt_token = load_youtrack_token()
    yt_headers = {
        "Authorization": f"Bearer {yt_token}",
        "Accept": "application/json",
    }

    is_work = prompt_yes_no("Is this work", default_yes=True)
    project_name = WORK_INBOX_NAME if is_work else KEVIN_INBOX_NAME
    issue_domain = ISSUE_DOMAIN_BY_WORK[is_work]

    description = prompt_required("Description")
    ticket_link = input("Ticket link (optional): ").strip()

    summary = description.splitlines()[0].strip()
    if len(summary) > 120:
        summary = summary[:117] + "..."

    print(f">>> Resolving project {project_name!r}…")
    project_id = find_project_id(yt_headers, project_name)

    print(f">>> Resolving assignee {ASSIGNEE_LOGIN!r}…")
    assignee_id = find_user_id(yt_headers, ASSIGNEE_LOGIN)

    by_proto = find_project_custom_fields(yt_headers, project_id)

    print(f">>> Creating issue… (Issue domain: {issue_domain})")
    issue_id, issue_readable = create_issue(
        yt_headers, project_id, summary, description, issue_domain, assignee_id, by_proto
    )

    if ticket_link:
        try:
            field_id = resolve_field(by_proto, FIELD_TICKET_LINK, project_id)["attachment_id"]
            set_simple_field(yt_headers, issue_id, field_id, ticket_link)
        except Exception as e:
            print(f"WARN: failed to set 'Ticket link': {e}")

    issue_url = f"{YOUTRACK_BASE_URL}/issue/{issue_readable}"
    print(f"CREATED: {issue_readable} in {project_name} (Issue domain: {issue_domain})")
    print(f"URL: {issue_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

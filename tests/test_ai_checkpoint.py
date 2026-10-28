#!/usr/bin/env python3
"""Tests for ai-checkpoint. Every test builds its own git repository and recovery-history
directory in a temporary directory; no real CHECKPOINT.md or ~/.local/state is touched.

Run:  python3 tests/test_ai_checkpoint.py
"""

import datetime
import importlib.machinery
import importlib.util
import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai-checkpoint")


def load_tool():
    loader = importlib.machinery.SourceFileLoader("ai_checkpoint", TOOL)
    spec = importlib.util.spec_from_loader("ai_checkpoint", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


AC = load_tool()


def section(lane_id, note="first", tasks="- [ ] task one\n", ticket=True):
    ticket_line = f"Ticket: AI-99 — https://youtrack.kevininscoe.com/issue/AI-99\n" if ticket else ""
    return (f"## Lane {lane_id}\n\nStarted: 2026-10-19 19:50\nHost: test\n{ticket_line}\n"
            f"### Summary\n\nTest lane {lane_id}: {note}.\n\n### Collision scope\n\n- fixtures\n\n"
            f"### Workflow 1 — test\n{tasks}")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="ai-checkpoint-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "home")
        self.state = os.path.join(self.tmp, "state")
        os.makedirs(self.home)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("GIT_", "AI_CHECKPOINT_"))}
        self.env.update(HOME=self.home, AI_CHECKPOINT_STATE_DIR=self.state,
                        AI_CHECKPOINT_MAC_HOME=os.path.join(self.tmp, "no-mac-home"),
                        AI_CHECKPOINT_LOCK_WAIT="2", GIT_CONFIG_NOSYSTEM="1",
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        self.repo = self.make_repo("repo")
        self.ckpt = os.path.join(self.repo, "CHECKPOINT.md")

    def make_repo(self, name):
        path = os.path.join(self.tmp, name)
        self.git("init", "-q", "-b", "main", path, cwd=self.tmp)
        with open(os.path.join(path, "README.md"), "w") as handle:
            handle.write("x\n")
        self.git("add", "README.md", cwd=path)
        self.git("-c", "commit.gpgsign=false", "commit", "-q", "-m", "init", cwd=path)
        return path

    def git(self, *args, cwd):
        subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def run_tool(self, *args, cwd=None, env=None, stdin=None):
        proc = subprocess.run([sys.executable, TOOL, *args], cwd=cwd or self.repo,
                              env=env or self.env, input=stdin, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True)
        return proc.returncode, proc.stdout, proc.stderr

    def write_section(self, text, name="section.md"):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def add(self, lane_id, note="first", **kwargs):
        rc, out, err = self.run_tool("add", "--lane", lane_id, "--section",
                                     self.write_section(section(lane_id, note), f"{lane_id}.md"),
                                     **kwargs)
        self.assertEqual(rc, 0, err)
        return out

    def update(self, lane_id, note, **kwargs):
        return self.run_tool("update", "--lane", lane_id, "--section",
                             self.write_section(section(lane_id, note), f"{lane_id}-u.md"),
                             **kwargs)

    def read(self, path=None):
        with open(path or self.ckpt, "rb") as handle:
            return handle.read()

    def fingerprint(self, path=None):
        info = os.stat(path or self.ckpt)
        return self.read(path), info.st_mtime_ns, info.st_ino, stat.S_IMODE(info.st_mode)

    def versions(self):
        found = []
        for repo_id in os.listdir(self.state):
            folder = os.path.join(self.state, repo_id, "versions")
            for name in sorted(os.listdir(folder)):
                if name.endswith(".json"):
                    with open(os.path.join(folder, name)) as handle:
                        found.append(json.load(handle))
        return found

    def version_content(self, record):
        path = os.path.join(self.state, record["repository_id"], "versions",
                            record["version"] + ".md")
        with open(path, "rb") as handle:
            return handle.read()

    def assert_clean(self):
        leftovers = [n for n in os.listdir(self.repo) if n.startswith(".ai-checkpoint-tmp.")]
        self.assertEqual(leftovers, [])
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".git", "ai-lanes.lock")))


class CreationAndValidation(Base):
    def test_first_creation_writes_header_and_lane_atomically(self):
        self.assertFalse(os.path.exists(self.ckpt))
        self.add("lane-a")
        text = self.read().decode()
        self.assertTrue(text.startswith("# CHECKPOINT — repo\n"))
        self.assertIn("## Lane lane-a\n", text)
        self.assertTrue(text.endswith("- [ ] task one\n"))
        self.assert_clean()

    def test_interrupted_first_creation_leaves_no_checkpoint(self):
        env = dict(self.env, AI_CHECKPOINT_TEST_HOOK="fail:publish")
        rc, _, err = self.run_tool("add", "--lane", "lane-a", "--section",
                                   self.write_section(section("lane-a")), env=env)
        self.assertEqual(rc, 1, err)
        self.assertIn("checkpoint unchanged", err)
        self.assertFalse(os.path.exists(self.ckpt))
        self.assert_clean()

    def test_failed_generation_and_bad_sections_leave_original_unchanged(self):
        self.add("lane-a")
        before = self.fingerprint()
        bad = {
            "empty": "",
            "wrong lane id": section("lane-b"),
            "two lanes": section("lane-a") + "\n" + section("lane-z"),
            "no summary": section("lane-a").replace("### Summary", "### Something"),
            "no collision scope": section("lane-a").replace("- fixtures\n", ""),
            "placeholder ticket": section("lane-a").replace(
                "Ticket: AI-99 — https://youtrack.kevininscoe.com/issue/AI-99", "Ticket: N/A"),
            "no tasks": section("lane-a", tasks="nothing yet\n"),
            "no started": section("lane-a").replace("Started: 2026-10-19 19:50\n", ""),
            "malformed heading": section("lane-a").replace("## Lane lane-a",
                                                           "## Lane lane-a extra"),
        }
        for label, text in bad.items():
            with self.subTest(label):
                rc, _, err = self.run_tool("update", "--lane", "lane-a", "--section",
                                           self.write_section(text))
                self.assertIn(rc, (6,), f"{label}: {err}")
                self.assertEqual(self.fingerprint(), before)
        rc, _, err = self.run_tool("update", "--lane", "lane-a", "--section",
                                   os.path.join(self.tmp, "missing.md"))
        self.assertEqual(rc, 2, err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()

    def test_malformed_generated_result_is_rejected(self):
        self.add("lane-a")
        self.add("lane-b")
        before = self.fingerprint()
        env = dict(self.env, AI_CHECKPOINT_TEST_HOOK="corrupt:result")
        rc, _, err = self.update("lane-a", "second", env=env)
        self.assertEqual(rc, 6, err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()

    def test_change_to_another_lane_is_rejected(self):
        for op in ("update", "add", "remove"):
            with self.subTest(op=op):
                shutil.rmtree(self.state, ignore_errors=True)
                if os.path.exists(self.ckpt):
                    os.unlink(self.ckpt)
                self.add("lane-a")
                self.add("lane-b")
                before = self.fingerprint()
                env = dict(self.env, AI_CHECKPOINT_TEST_HOOK="corrupt:other")
                if op == "update":
                    rc, _, err = self.update("lane-b", "second", env=env)
                elif op == "add":
                    rc, _, err = self.run_tool("add", "--lane", "lane-c", "--section",
                                               self.write_section(section("lane-c")), env=env)
                else:
                    rc, _, err = self.run_tool("remove", "--lane", "lane-b", env=env)
                self.assertEqual(rc, 6, err)
                self.assertIn("must not touch", err)
                self.assertEqual(self.fingerprint(), before)

    def test_missing_lane_update_fails_and_remove_reports(self):
        self.add("lane-a")
        before = self.fingerprint()
        rc, _, err = self.run_tool("update", "--lane", "lane-x", "--section",
                                   self.write_section(section("lane-x")))
        self.assertEqual(rc, 3, err)
        rc, _, err = self.run_tool("remove", "--lane", "lane-x")
        self.assertEqual(rc, 3, err)
        self.assertIn("not in", err)
        rc, _, err = self.run_tool("add", "--lane", "lane-a", "--section",
                                   self.write_section(section("lane-a")))
        self.assertEqual(rc, 4, err)
        self.assertEqual(self.fingerprint(), before)

    def test_damaged_empty_checkpoint_is_refused_then_restorable(self):
        self.add("lane-a")
        good = self.read()
        with open(self.ckpt, "w"):
            pass   # what the failed awk edit left behind
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 6, err)
        self.assertEqual(self.read(), b"")
        good_version = [r for r in self.versions() if r["kind"] == "after"][-1]["version"]
        rc, out, err = self.run_tool("restore", good_version, "--lane", "lane-a", "--yes")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.read(), good)
        saved_empty = [r for r in self.versions() if r["kind"] == "before"][-1]
        self.assertEqual(saved_empty["size"], 0)

    def test_symlinked_checkpoint_is_refused(self):
        target = os.path.join(self.tmp, "elsewhere.md")
        with open(target, "w") as handle:
            handle.write(section("lane-a"))
        os.symlink(target, self.ckpt)
        rc, _, err = self.update("lane-a", "x")
        self.assertEqual(rc, 1, err)
        self.assertTrue(os.path.islink(self.ckpt))


class Preservation(Base):
    def test_update_preserves_other_lanes_byte_for_byte(self):
        odd_b = section("lane-b").replace("- [ ] task one", "- [ ] task one   \n\n\n- [x] two\t")
        handmade = (AC.HEADER_TEMPLATE.format(name="repo") + section("lane-a") + "\n\n\n"
                    + odd_b + "\n" + section("lane-c") + "\n")
        with open(self.ckpt, "w", encoding="utf-8") as handle:
            handle.write(handmade)
        old = AC.parse(handmade, "fixture")
        rc, _, err = self.update("lane-b", "second")
        self.assertEqual(rc, 0, err)
        new = AC.parse(self.read().decode(), "result")
        self.assertEqual(new.preamble, old.preamble)
        self.assertEqual(new.get("lane-a").body + new.get("lane-a").sep,
                         old.get("lane-a").body + old.get("lane-a").sep)
        self.assertEqual(new.get("lane-c").body, old.get("lane-c").body)
        self.assertIn("second", new.get("lane-b").body)
        self.assertEqual(new.ids(), ["lane-a", "lane-b", "lane-c"])

    def test_crlf_lanes_survive_another_lanes_update(self):
        crlf = section("lane-a").replace("\n", "\r\n")
        with open(self.ckpt, "wb") as handle:
            handle.write((AC.HEADER_TEMPLATE.format(name="repo")).encode() + crlf.encode()
                         + b"\r\n" + section("lane-b").encode())
        rc, _, err = self.update("lane-b", "second")
        self.assertEqual(rc, 0, err)
        self.assertIn(crlf.encode(), self.read())

    def test_permissions_survive_replacement(self):
        self.add("lane-a")
        for mode in (0o600, 0o640, 0o664):
            with self.subTest(mode=oct(mode)):
                os.chmod(self.ckpt, mode)
                rc, _, err = self.update("lane-a", f"mode {mode:o}")
                self.assertEqual(rc, 0, err)
                self.assertEqual(stat.S_IMODE(os.stat(self.ckpt).st_mode), mode)
        os.chmod(self.ckpt, 0o600)
        self.add("lane-b")
        self.assertEqual(stat.S_IMODE(os.stat(self.ckpt).st_mode), 0o600)

    def test_worktree_resolves_the_primary_checkout(self):
        worktree = os.path.join(self.repo, "ai-wt", "T-1")
        self.git("worktree", "add", "-q", "-b", "T-1", worktree, cwd=self.repo)
        self.add("lane-a", cwd=worktree)
        self.assertTrue(os.path.exists(self.ckpt))
        self.assertFalse(os.path.exists(os.path.join(worktree, "CHECKPOINT.md")))


class History(Base):
    def test_remove_last_lane_saves_and_records_intentional_deletion(self):
        self.add("lane-a")
        last = self.read()
        rc, out, err = self.run_tool("remove", "--lane", "lane-a")
        self.assertEqual(rc, 0, err)
        self.assertFalse(os.path.exists(self.ckpt))
        records = self.versions()
        self.assertEqual(records[-1]["kind"], "deleted")
        self.assertEqual(records[-2]["kind"], "before")
        self.assertEqual(self.version_content(records[-2]), last)
        self.assertEqual(records[-1]["previous"], records[-2]["version"])
        self.assert_clean()

    def test_removing_one_of_two_lanes_keeps_the_other_and_the_file(self):
        self.add("lane-a")
        self.add("lane-b")
        b_body = AC.parse(self.read().decode(), "x").get("lane-b").body
        rc, _, err = self.run_tool("remove", "--lane", "lane-a")
        self.assertEqual(rc, 0, err)
        doc = AC.parse(self.read().decode(), "x")
        self.assertEqual(doc.ids(), ["lane-b"])
        self.assertEqual(doc.get("lane-b").body, b_body)

    def test_metadata_records_origin_and_checksum(self):
        self.add("lane-a")
        record = self.versions()[-1]
        for key in ("host", "primary_checkout", "utc", "operation", "lane", "sha256",
                    "repository_id", "transaction"):
            self.assertTrue(record.get(key), key)
        self.assertEqual(record["host"], socket.gethostname())
        self.assertEqual(record["primary_checkout"], self.repo)
        self.assertEqual(AC.sha256(self.version_content(record)), record["sha256"])

    def test_history_is_private_and_independent_of_the_live_file(self):
        self.add("lane-a")
        record = self.versions()[-1]
        folder = os.path.join(self.state, record["repository_id"], "versions")
        for path in (self.state, os.path.dirname(folder), folder):
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o700, path)
        copy = os.path.join(folder, record["version"] + ".md")
        self.assertEqual(stat.S_IMODE(os.stat(copy).st_mode), 0o600)
        self.assertNotEqual(os.stat(copy).st_ino, os.stat(self.ckpt).st_ino)
        self.assertEqual(os.stat(copy).st_nlink, 1)
        self.assertEqual(os.stat(self.ckpt).st_nlink, 1)

    def test_recovery_storage_failure_prevents_publication(self):
        self.add("lane-a")
        before = self.fingerprint()
        blocker = os.path.join(self.tmp, "a-file")
        with open(blocker, "w") as handle:
            handle.write("not a directory\n")
        env = dict(self.env, AI_CHECKPOINT_STATE_DIR=os.path.join(blocker, "state"))
        rc, _, err = self.update("lane-a", "second", env=env)
        self.assertEqual(rc, 7, err)
        self.assertEqual(self.fingerprint(), before)
        env = dict(self.env, AI_CHECKPOINT_TEST_HOOK="fail:history")
        rc, _, err = self.update("lane-a", "second", env=env)
        self.assertEqual(rc, 7, err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()

    def test_failure_after_publication_says_it_took_effect(self):
        self.add("lane-a")
        env = dict(self.env, AI_CHECKPOINT_TEST_HOOK="fail:record")
        rc, _, err = self.update("lane-a", "second", env=env)
        self.assertEqual(rc, 8, err)
        self.assertIn("TOOK EFFECT", err)
        self.assertIn("Do not retry", err)
        self.assertIn(b"second", self.read())
        self.assert_clean()

    def test_rapid_operations_produce_unique_versions(self):
        self.add("lane-a")
        for i in range(25):
            rc, _, err = self.update("lane-a", f"update {i}")
            self.assertEqual(rc, 0, err)
        ids = [r["version"] for r in self.versions()]
        self.assertEqual(len(ids), 1 + 25 * 2)
        self.assertEqual(len(set(ids)), len(ids))

    def test_unique_ids_under_the_same_microsecond(self):
        os.environ["AI_CHECKPOINT_STATE_DIR"] = self.state
        self.addCleanup(os.environ.pop, "AI_CHECKPOINT_STATE_DIR", None)
        history = AC.History("0" * 32)
        history.ensure()
        frozen = AC.utc_now()
        original = AC.utc_now
        AC.utc_now = lambda: frozen
        self.addCleanup(setattr, AC, "utc_now", original)
        ids = {history.save("after", b"## Lane x\n", {"operation": "t"})["version"]
               for _ in range(200)}
        self.assertEqual(len(ids), 200)

    def test_restore_saves_current_first_and_needs_confirmation(self):
        self.add("lane-a")
        self.add("lane-b")
        old_version = [r for r in self.versions() if r["kind"] == "after"][0]["version"]
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 0, err)
        current = self.read()
        rc, out, err = self.run_tool("restore", old_version, "--lane", "lane-a")
        self.assertEqual(rc, 9, err)
        self.assertIn("lane-b", err)       # restoring removes lane-b: a takeover
        self.assertIn("lanes in that version: lane-a", out)
        self.assertEqual(self.read(), current)
        rc, out, err = self.run_tool("restore", old_version, "--lane", "lane-a",
                                     "--takeover-approved", "test")
        self.assertEqual(rc, 9, err)
        self.assertIn("preview only", err)
        self.assertEqual(self.read(), current)
        rc, out, err = self.run_tool("restore", old_version, "--lane", "lane-a",
                                     "--takeover-approved", "test", "--yes")
        self.assertEqual(rc, 0, err)
        self.assertEqual(self.read(), self.version_content(
            [r for r in self.versions() if r["version"] == old_version][0]))
        before = [r for r in self.versions() if r["kind"] == "before"][-1]
        self.assertEqual(before["operation"], "restore")
        self.assertEqual(self.version_content(before), current)
        self.assertEqual(self.versions()[-1]["restored_from"], old_version)

    def test_restore_never_happens_by_itself(self):
        self.add("lane-a")
        self.run_tool("remove", "--lane", "lane-a")
        for command in (["status"], ["history"], ["where"]):
            self.run_tool(*command)
        self.assertFalse(os.path.exists(self.ckpt))
        rc, out, _ = self.run_tool("status")
        self.assertIn("absent", out)

    def test_diff_and_show(self):
        self.add("lane-a")
        rc, _, err = self.update("lane-a", "second")
        first = [r for r in self.versions() if r["kind"] == "after"][0]["version"]
        rc, out, err = self.run_tool("diff", first)
        self.assertEqual(rc, 0, err)
        self.assertIn("-Test lane lane-a: first.", out)
        self.assertIn("+Test lane lane-a: second.", out)
        rc, out, err = self.run_tool("show", first)
        self.assertIn("lane-a", out)
        self.assertIn("sha256:", out)
        rc, out, err = self.run_tool("history")
        self.assertEqual(rc, 0, err)
        self.assertEqual(len([l for l in out.splitlines() if l[:1].isdigit()]), 3)


class Retention(Base):
    def make_version(self, repo_id, age_days, kind="after"):
        stamp = AC.utc_now() - datetime.timedelta(days=age_days)
        version = f"{stamp.strftime('%Y%m%dT%H%M%S.%fZ')}-{os.urandom(4).hex()}"
        folder = os.path.join(self.state, repo_id, "versions")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, version + ".json"), "w") as handle:
            json.dump({"version": version, "utc": AC.iso(stamp), "kind": kind}, handle)
        with open(os.path.join(folder, version + ".md"), "w") as handle:
            handle.write("x\n")
        return os.path.join(folder, version)

    def test_retention_removes_only_expired_history(self):
        a, b = "a" * 32, "b" * 32
        old = [self.make_version(a, 91), self.make_version(b, 400)]
        kept = [self.make_version(a, 89), self.make_version(b, 0), self.make_version(a, 30)]
        stranger = os.path.join(self.state, a, "versions", "notes.txt")
        with open(stranger, "w") as handle:
            handle.write("not ours\n")
        other_dir = os.path.join(self.state, "not-a-repo-id")
        os.makedirs(other_dir)
        rc, out, err = self.run_tool("prune", "--dry-run")
        self.assertIn("would remove 4 file(s)", out)
        self.assertTrue(all(os.path.exists(p + ".json") for p in old))
        self.add("lane-a")    # every successful mutation enforces retention
        for path in old:
            self.assertFalse(os.path.exists(path + ".json"))
            self.assertFalse(os.path.exists(path + ".md"))
        for path in kept:
            self.assertTrue(os.path.exists(path + ".json"))
            self.assertTrue(os.path.exists(path + ".md"))
        self.assertTrue(os.path.exists(stranger))
        self.assertTrue(os.path.isdir(other_dir))


class Identity(Base):
    def repo_id(self, path):
        with open(os.path.join(path, ".git", "ai-checkpoint-id")) as handle:
            return handle.read().strip()

    def test_separate_clones_of_one_remote_have_separate_histories(self):
        clone_a = os.path.join(self.tmp, "clone-a")
        clone_b = os.path.join(self.tmp, "clone-b")
        self.git("clone", "-q", self.repo, clone_a, cwd=self.tmp)
        self.git("clone", "-q", self.repo, clone_b, cwd=self.tmp)
        self.add("lane-a", cwd=clone_a)
        self.add("lane-a", cwd=clone_b)
        self.assertNotEqual(self.repo_id(clone_a), self.repo_id(clone_b))
        self.assertEqual(len([n for n in os.listdir(self.state) if len(n) == 32]), 2)

    def test_two_paths_to_one_checkout_share_identity_lock_and_history(self):
        # The Mac sees ~/Projects/x; mac-container sees /mac-home/Projects/x (via a symlink).
        mac_home = os.path.join(self.tmp, "mac-user-home")
        os.makedirs(os.path.join(mac_home, "Projects"))
        real = os.path.join(mac_home, "Projects", "shared")
        shutil.move(self.repo, real)
        alias_root = os.path.join(self.tmp, "container-home")
        os.makedirs(alias_root)
        alias = os.path.join(alias_root, "Projects")
        os.symlink(os.path.join(mac_home, "Projects"), alias)
        mac_env = dict(self.env, HOME=mac_home)
        mac_env.pop("AI_CHECKPOINT_STATE_DIR")
        mac_env["AI_CHECKPOINT_MAC_HOME"] = os.path.join(self.tmp, "absent")
        box_env = dict(self.env, HOME=alias_root)
        box_env.pop("AI_CHECKPOINT_STATE_DIR")
        box_env["AI_CHECKPOINT_MAC_HOME"] = mac_home       # the container's /mac-home
        rc, _, err = self.run_tool("add", "--lane", "mac-lane", "--section",
                                   self.write_section(section("mac-lane")), cwd=real, env=mac_env)
        self.assertEqual(rc, 0, err)
        rc, _, err = self.run_tool("add", "--lane", "box-lane", "--section",
                                   self.write_section(section("box-lane")),
                                   cwd=os.path.join(alias, "shared"), env=box_env)
        self.assertEqual(rc, 0, err)
        _, mac_where, _ = self.run_tool("where", cwd=real, env=mac_env)
        _, box_where, _ = self.run_tool("where", cwd=os.path.join(alias, "shared"), env=box_env)
        field = lambda text, key: [l.split(None, 1)[1] for l in text.splitlines()
                                   if l.startswith(key)][0]
        self.assertEqual(field(mac_where, "repository:"), field(box_where, "repository:"))
        self.assertTrue(os.path.samefile(os.path.dirname(field(mac_where, "lock:")),
                                         os.path.dirname(field(box_where, "lock:"))))
        self.assertEqual(os.path.realpath(field(mac_where, "history:")),
                         os.path.realpath(field(box_where, "history:")))
        history = os.path.join(mac_home, ".local", "state", "ai-checkpoints")
        self.assertEqual(len(os.listdir(history)), 1)
        with open(os.path.join(real, "CHECKPOINT.md")) as handle:
            self.assertEqual(AC.parse(handle.read(), "x").ids(), ["mac-lane", "box-lane"])

    def test_outside_git_needs_an_explicit_directory(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        rc, _, err = self.run_tool("add", "--lane", "lane-a", "--section",
                                   self.write_section(section("lane-a")), cwd=plain)
        self.assertEqual(rc, 2, err)
        self.assertIn("--dir", err)
        self.assertEqual(os.listdir(plain), [])
        rc, _, err = self.run_tool("add", "--dir", plain, "--lane", "lane-a", "--section",
                                   self.write_section(section("lane-a")), cwd=plain)
        self.assertEqual(rc, 0, err)
        self.assertEqual(sorted(os.listdir(plain)), [".ai-checkpoint-id", "CHECKPOINT.md"])
        rc, _, err = self.run_tool("add", "--dir", self.repo, "--lane", "lane-a", "--section",
                                   self.write_section(section("lane-a")))
        self.assertEqual(rc, 2, err)


class Locking(Base):
    def lock_path(self):
        return os.path.join(self.repo, ".git", "ai-lanes.lock")

    def plant_lock(self, owner, age_seconds=0):
        os.mkdir(self.lock_path())
        with open(os.path.join(self.lock_path(), "owner"), "w") as handle:
            handle.write(owner if isinstance(owner, str) else json.dumps(owner))
        if age_seconds:
            old = time.time() - age_seconds
            os.utime(self.lock_path(), (old, old))

    def me(self, **changes):
        owner = {"tool": "ai-checkpoint", "lane": "other", "operation": "update",
                 "host": socket.gethostname(), "machine": AC.machine_id(), "boot": AC.boot_id(),
                 "pidns": AC.pid_namespace(), "pid": os.getpid(),
                 "pid_start": AC.pid_start(os.getpid()), "utc": AC.iso(AC.utc_now()),
                 "nonce": "feedfacefeedface"}
        owner.update(changes)
        return owner

    def test_live_holder_is_waited_for_and_reported_never_broken(self):
        self.add("lane-a")
        before = self.fingerprint()
        self.plant_lock(self.me(), age_seconds=3600)
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 5, err)
        self.assertIn("fingerprint", err)
        self.assertTrue(os.path.isdir(self.lock_path()))
        self.assertEqual(self.fingerprint(), before)

    def test_old_lock_from_another_machine_is_never_broken_by_age(self):
        self.add("lane-a")
        before = self.fingerprint()
        self.plant_lock(self.me(machine="mac-uuid", host="KevinI-MBP24", pid=999999999),
                        age_seconds=7 * 86400)
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 5, err)
        self.assertIn("another machine", err)
        self.assertEqual(self.fingerprint(), before)

    def test_other_pid_namespace_is_not_judged_by_pid(self):
        if not AC.pid_namespace():
            self.skipTest("no PID namespaces on this platform")
        self.add("lane-a")
        self.plant_lock(self.me(pidns="pid:[1]", pid=999999999), age_seconds=600)
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 5, err)
        self.assertIn("PID namespace", err)

    def test_legacy_owner_line_is_not_broken_by_age(self):
        self.add("lane-a")
        self.plant_lock(f"old-lane {socket.gethostname()} 2026-10-19 10:00:00", age_seconds=600)
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 5, err)

    def test_lock_of_an_exited_process_on_this_machine_is_cleared(self):
        if not AC.machine_id():
            self.skipTest("no machine id on this host")
        self.add("lane-a")
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()
        self.plant_lock(self.me(pid=gone.pid, pid_start="0"))
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 0, err)
        self.assertIn("removed a stale checkpoint lock", err)
        self.assertIn(b"second", self.read())

    def test_lock_from_before_a_reboot_is_cleared(self):
        if not AC.machine_id() or not AC.boot_id():
            self.skipTest("no machine or boot id on this host")
        self.add("lane-a")
        self.plant_lock(self.me(boot="an-earlier-boot"))
        rc, _, err = self.update("lane-a", "second")
        self.assertEqual(rc, 0, err)
        self.assertIn("rebooted", err)

    def test_break_lock_needs_the_inspected_fingerprint(self):
        self.plant_lock(self.me(machine="elsewhere"))
        rc, out, _ = self.run_tool("lock-status")
        fingerprint = [l.split()[1] for l in out.splitlines() if l.startswith("fingerprint:")][0]
        rc, _, err = self.run_tool("break-lock", "--expect", "0-0-wrong")
        self.assertEqual(rc, 5, err)
        self.assertTrue(os.path.isdir(self.lock_path()))
        rc, _, err = self.run_tool("break-lock", "--expect", fingerprint)
        self.assertEqual(rc, 0, err)
        self.assertFalse(os.path.exists(self.lock_path()))

    def test_concurrent_writers_never_lose_each_others_changes(self):
        self.add("seed")
        writers = 8
        env = dict(self.env, AI_CHECKPOINT_LOCK_WAIT="60")
        script = (
            "import subprocess, sys\n"
            "tool, lane, folder = sys.argv[1:]\n"
            "def run(cmd, note):\n"
            "    path = f'{folder}/{lane}-{note}.md'\n"
            "    with open(path, 'w') as handle:\n"
            "        handle.write(SECTION.replace('LANE', lane).replace('NOTE', note))\n"
            "    rc = subprocess.run([sys.executable, tool, cmd, '--lane', lane, '--section', path]).returncode\n"
            "    assert rc == 0, (lane, cmd, rc)\n"
            "run('add', 'n0')\n"
            "for i in range(1, 6):\n"
            "    run('update', f'n{i}')\n"
        )
        script = "SECTION = " + repr(section("LANE", "NOTE")) + "\n" + script
        procs = [subprocess.Popen([sys.executable, "-c", script, TOOL, f"w{i}", self.tmp],
                                  cwd=self.repo, env=env, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE, text=True) for i in range(writers)]
        for proc in procs:
            _, err = proc.communicate(timeout=300)
            self.assertEqual(proc.returncode, 0, err)
        doc = AC.parse(self.read().decode(), "final")
        self.assertEqual(sorted(doc.ids()), sorted(["seed"] + [f"w{i}" for i in range(writers)]))
        for i in range(writers):
            self.assertIn("Test lane w%d: n5." % i, doc.get(f"w{i}").body)
        self.assertEqual(len(self.versions()), 1 + writers * 6 * 2)   # seed, then before+after each
        self.assert_clean()

    def test_sigterm_before_publication_keeps_the_original(self):
        self.add("lane-a")
        before = self.fingerprint()
        env = dict(self.env, AI_CHECKPOINT_TEST_HOOK="sleep:publish")
        proc = subprocess.Popen([sys.executable, TOOL, "update", "--lane", "lane-a", "--section",
                                 self.write_section(section("lane-a", "second"))],
                                cwd=self.repo, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        deadline = time.time() + 20
        while time.time() < deadline and not any(
                n.startswith(".ai-checkpoint-tmp.") for n in os.listdir(self.repo)):
            time.sleep(0.05)
        time.sleep(0.2)
        proc.send_signal(signal.SIGTERM)
        _, err = proc.communicate(timeout=30)
        self.assertEqual(proc.returncode, 1, err)
        self.assertIn("checkpoint unchanged", err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()


# A checkpoint written before lane sections existed: whole-file, with its own '## ' headings
# and unfinished tasks, followed by a blank line and then the lane sections. This is the shape
# of host-rpi5-core-config/CHECKPOINT.md (PIM-18's record) that blocked the removal of a
# finished KHC-134 lane.
LEGACY = (
    "# CHECKPOINT — create-reminder.py credential wrapper for core (PIM-18)\n\n"
    "Started: 2026-09-26 12:02 (America/New_York)\n"
    "YouTrack issue: PIM-18 — https://youtrack.kevininscoe.com/issue/PIM-18\n\n"
    "## Summary\n\nAn agent is giving core a credential wrapper.\n\n"
    "## Workflow 1 — Code and configuration\n"
    "- [ ] pim: host-neutral scripts/create-reminder/run-with-credentials.sh\n"
    "- [x] host-rpi5-core-config: policy rule + local profile — completed 12:07\n\n"
    "## Notes\nSeparate issue for core's rejected broker SecretID.\n\n"
)
DONE = "- [x] finished task\n"


class LegacyRecord(Base):
    """Removing a finished lane must not be blocked by, or damage, an older record in the file."""

    def write_checkpoint(self, *lanes):
        text = LEGACY + "".join(lane for lane in lanes)
        with open(self.ckpt, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(self.ckpt, 0o664)

    def lane_text(self, lane_id, tasks=DONE):
        return section(lane_id, "finished", tasks)

    def test_removing_the_only_lane_keeps_the_file_and_the_legacy_record_exactly(self):
        self.write_checkpoint(self.lane_text("khc-134"))
        before_mode = stat.S_IMODE(os.stat(self.ckpt).st_mode)
        rc, out, err = self.run_tool("remove", "--lane", "khc-134")
        self.assertEqual(rc, 0, err)
        self.assertIn("kept", out)
        self.assertEqual(self.read(), LEGACY.encode(), "legacy bytes changed")
        self.assertEqual(stat.S_IMODE(os.stat(self.ckpt).st_mode), before_mode)
        kinds = [r["kind"] for r in self.versions()]
        self.assertEqual(kinds[-2:], ["before", "after"])
        self.assertNotIn("deleted", kinds)
        self.assert_clean()

    def test_the_removed_lane_is_recoverable_from_history(self):
        original = (LEGACY + self.lane_text("khc-134")).encode()
        self.write_checkpoint(self.lane_text("khc-134"))
        self.assertEqual(self.run_tool("remove", "--lane", "khc-134")[0], 0)
        before = [r for r in self.versions() if r["kind"] == "before"][-1]
        self.assertEqual(self.version_content(before), original)

    def test_legacy_record_survives_removal_of_each_of_several_lanes(self):
        a, b = self.lane_text("lane-a"), self.lane_text("lane-b")
        self.write_checkpoint(a, "\n" + b)
        self.assertEqual(self.run_tool("remove", "--lane", "lane-a")[0], 0)
        doc = AC.parse(self.read().decode(), "x")
        self.assertEqual(doc.ids(), ["lane-b"])
        self.assertEqual(doc.preamble, LEGACY)
        self.assertEqual(doc.get("lane-b").body, b.rstrip("\n") + "\n")
        self.assertEqual(self.run_tool("remove", "--lane", "lane-b")[0], 0)
        self.assertEqual(self.read(), LEGACY.encode())

    def test_a_lane_can_be_added_to_the_file_the_removal_left(self):
        self.write_checkpoint(self.lane_text("khc-134"))
        self.assertEqual(self.run_tool("remove", "--lane", "khc-134")[0], 0)
        rc, _, err = self.run_tool("add", "--lane", "next", "--section",
                                   self.write_section(section("next")))
        self.assertEqual(rc, 0, err)
        doc = AC.parse(self.read().decode(), "x")
        self.assertEqual(doc.ids(), ["next"])
        self.assertEqual(doc.preamble, LEGACY)

    def test_missing_lane_in_a_legacy_only_file_is_reported_and_nothing_changes(self):
        self.write_checkpoint()
        before = self.fingerprint()
        rc, _, err = self.run_tool("remove", "--lane", "nobody")
        self.assertEqual(rc, 3, err)
        rc, _, err = self.run_tool("update", "--lane", "nobody", "--section",
                                   self.write_section(section("nobody")))
        self.assertEqual(rc, 3, err)
        self.assertEqual(self.fingerprint(), before)

    def test_status_reports_the_legacy_record_without_a_warning(self):
        self.write_checkpoint()
        rc, out, err = self.run_tool("status")
        self.assertEqual(rc, 0, err)
        self.assertIn("outside any lane", out)
        self.assertNotIn("WARNING", out)

    def test_ambiguous_target_lane_is_refused_and_nothing_changes(self):
        # A '## ' heading inside the lane may be another record pasted after it.
        stray = self.lane_text("khc-134") + "\n## Another record\n- [ ] unfinished elsewhere\n"
        self.write_checkpoint(stray)
        before = self.fingerprint()
        rc, _, err = self.run_tool("remove", "--lane", "khc-134")
        self.assertEqual(rc, 6, err)
        self.assertIn("ambiguous", err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()

    def test_ambiguity_is_refused_without_legacy_content_too(self):
        self.add("lane-a")
        with open(self.ckpt, "a") as handle:
            handle.write("\n## Another record\n")
        before = self.fingerprint()
        rc, _, err = self.run_tool("remove", "--lane", "lane-a")
        self.assertEqual(rc, 6, err)
        self.assertEqual(self.fingerprint(), before)

    def test_malformed_lane_heading_still_refuses_everything(self):
        self.write_checkpoint(self.lane_text("khc-134"), "\n## Lane\n- [ ] x\n")
        before = self.fingerprint()
        rc, _, err = self.run_tool("remove", "--lane", "khc-134")
        self.assertEqual(rc, 6, err)
        self.assertEqual(self.fingerprint(), before)

    def test_header_only_file_without_lanes_is_still_treated_as_damaged(self):
        self.add("lane-a")
        header = AC.parse(self.read().decode(), "x").preamble
        with open(self.ckpt, "w", newline="") as handle:
            handle.write(header)
        before = self.fingerprint()
        rc, _, err = self.update("lane-a", "again")
        self.assertEqual(rc, 6, err)
        rc, _, err = self.run_tool("add", "--lane", "lane-b", "--section",
                                   self.write_section(section("lane-b")))
        self.assertEqual(rc, 6, err)
        self.assertEqual(self.fingerprint(), before)

    def test_without_legacy_content_the_last_lane_still_deletes_the_file(self):
        self.add("lane-a")
        self.assertEqual(self.run_tool("remove", "--lane", "lane-a")[0], 0)
        self.assertFalse(os.path.exists(self.ckpt))


class Migration(Base):
    """'migrate' rewrites legacy '## Lane ID <text>' headings and nothing else (AI-106)."""

    APPROVE = ("--yes", "--approved", "test fixture")

    def write_checkpoint(self, text):
        with open(self.ckpt, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(self.ckpt, 0o664)

    def legacy_file(self):
        good = section("lane-good")
        bad = section("ABC-123").replace("## Lane ABC-123\n",
                                          "## Lane ABC-123 — example title — PAUSED 2026-10-22\n", 1)
        text = AC.HEADER_TEMPLATE.format(name="repo") + good + "\n" + bad
        self.write_checkpoint(text)
        return text, good, bad

    def test_preview_is_the_default_and_changes_nothing(self):
        self.legacy_file()
        before = self.fingerprint()
        rc, out, err = self.run_tool("migrate")
        self.assertEqual(rc, 9, err)
        self.assertIn("line ", out)
        self.assertIn("+Title: example title — PAUSED 2026-10-22", out)
        self.assertIn("NOT MIGRATED", err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()

    def test_yes_without_approval_is_refused(self):
        self.legacy_file()
        before = self.fingerprint()
        rc, _, err = self.run_tool("migrate", "--yes")
        self.assertEqual(rc, 9, err)
        self.assertEqual(self.fingerprint(), before)

    def test_migration_rewrites_only_the_heading_and_keeps_its_text(self):
        text, good, bad = self.legacy_file()
        rc, out, err = self.run_tool("migrate", *self.APPROVE)
        self.assertEqual(rc, 0, err)
        new = self.read().decode()
        doc = AC.parse(new, "x")
        self.assertEqual(doc.ids(), ["lane-good", "ABC-123"])
        self.assertEqual(doc.get("lane-good").body, good)
        expected = text.replace("## Lane ABC-123 — example title — PAUSED 2026-10-22\n",
                                "## Lane ABC-123\n\nTitle: example title — PAUSED 2026-10-22\n", 1)
        self.assertEqual(new, expected)
        self.assertEqual(stat.S_IMODE(os.stat(self.ckpt).st_mode), 0o664)
        self.assert_clean()

    def test_the_original_is_recoverable_and_the_approval_is_recorded(self):
        text, _, _ = self.legacy_file()
        self.assertEqual(self.run_tool("migrate", *self.APPROVE)[0], 0)
        records = self.versions()
        before = [r for r in records if r["kind"] == "before"][-1]
        self.assertEqual(before["operation"], "migrate")
        self.assertEqual(self.version_content(before), text.encode())

    def test_lanes_can_be_changed_after_migration(self):
        self.legacy_file()
        self.assertEqual(self.run_tool("migrate", *self.APPROVE)[0], 0)
        self.assertEqual(self.run_tool("remove", "--lane", "lane-good")[0], 0)
        self.assertEqual(AC.parse(self.read().decode(), "x").ids(), ["ABC-123"])

    def test_parenthesised_trailing_text_and_crlf(self):
        text = (AC.HEADER_TEMPLATE.format(name="repo")
                + "## Lane XYZ-19 (Claude Code, laptop)\r\n\r\n- [x] done\r\n")
        self.write_checkpoint(text)
        self.assertEqual(self.run_tool("migrate", *self.APPROVE)[0], 0)
        self.assertEqual(self.read().decode(), text.replace(
            "## Lane XYZ-19 (Claude Code, laptop)\r\n",
            "## Lane XYZ-19\r\n\r\nTitle: (Claude Code, laptop)\r\n", 1))

    def test_a_current_file_is_a_noop(self):
        self.add("lane-a")
        before = self.fingerprint()
        rc, out, err = self.run_tool("migrate", *self.APPROVE)
        self.assertEqual(rc, 0, err)
        self.assertIn("nothing to migrate", out)
        self.assertEqual(self.fingerprint(), before)

    def test_absent_file_is_a_noop(self):
        rc, out, err = self.run_tool("migrate", *self.APPROVE)
        self.assertEqual(rc, 0, err)
        self.assertFalse(os.path.exists(self.ckpt))

    def test_a_heading_without_an_id_is_refused(self):
        self.write_checkpoint(AC.HEADER_TEMPLATE.format(name="repo") + section("lane-a")
                              + "\n## Lane\n- [ ] x\n")
        before = self.fingerprint()
        rc, _, err = self.run_tool("migrate", *self.APPROVE)
        self.assertEqual(rc, 6, err)
        self.assertIn("no usable lane id", err)
        self.assertEqual(self.fingerprint(), before)

    def test_a_migration_that_would_duplicate_a_lane_id_is_refused(self):
        # The same session wrote a second section for a second ticket. Seen in a real checkpoint.
        self.write_checkpoint(AC.HEADER_TEMPLATE.format(name="repo") + section("s1a2") + "\n"
                              + section("s1a2").replace("## Lane s1a2\n",
                                                        "## Lane s1a2 — DEF-42\n", 1))
        before = self.fingerprint()
        rc, _, err = self.run_tool("migrate", *self.APPROVE)
        self.assertEqual(rc, 6, err)
        self.assertIn("more than once", err)
        self.assertEqual(self.fingerprint(), before)
        self.assert_clean()


if __name__ == "__main__":
    unittest.main(verbosity=2)

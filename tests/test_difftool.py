#!/usr/bin/env python3
"""Tests for difftool. Every test builds a real Git repository in a temporary directory.

Run:  python3 tests/test_difftool.py
"""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "difftool")
REAL_GIT = shutil.which("git")
NO_DIFFERENCES = "No differences for this comparison"


def snapshot(root, skip):
    """Record every file under root: type, mode, size, mtime, link target and content hash."""
    seen = {}
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if os.path.join(folder, d) != skip]
        for name in dirs + files:
            path = os.path.join(folder, name)
            info = os.lstat(path)
            entry = [stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode)]
            if stat.S_ISLNK(info.st_mode):
                entry.append(os.readlink(path))
            elif stat.S_ISREG(info.st_mode):
                with open(path, "rb") as handle:
                    entry += [info.st_size, info.st_mtime_ns, hashlib.sha256(handle.read()).hexdigest()]
            seen[os.path.relpath(path, root)] = entry
    return seen


class DifftoolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="difftool-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "repo")
        self.out = os.path.join(self.tmp, "out")  # the only place a test lets difftool write
        home = os.path.join(self.tmp, "home")
        os.makedirs(self.out)
        os.makedirs(home)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env.update(
            HOME=home,
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_AUTHOR_NAME="Test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="Test",
            GIT_COMMITTER_EMAIL="test@example.invalid",
        )
        self.git("init", "-q", "-b", "main", self.repo, cwd=self.tmp)

    # -- helpers -----------------------------------------------------------

    def git(self, *args, cwd=None):
        proc = subprocess.run(
            [REAL_GIT, *args], cwd=cwd or self.repo, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if proc.returncode != 0:
            self.fail(f"git {args} failed: {proc.stderr.decode(errors='replace')}")
        return proc.stdout

    def sha(self, ref, cwd=None):
        return self.git("rev-parse", ref, cwd=cwd).decode().strip()

    def write(self, rel, data, repo=None):
        path = os.path.join(repo or self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data.encode() if isinstance(data, str) else data)
        return path

    def commit(self, message="commit", cwd=None):
        self.git("add", "-A", cwd=cwd)
        self.git("commit", "-q", "-m", message, cwd=cwd)

    def seed(self, rel="f.txt", data="one\n"):
        self.write(rel, data)
        self.commit("seed")

    def tool(self, *args, cwd=None, env=None):
        """Run difftool and fail the test if it changed anything outside self.out."""
        before = snapshot(self.tmp, self.out)
        proc = subprocess.run(
            [sys.executable, TOOL, *args],
            cwd=cwd or self.repo,
            env=env or self.env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(before, snapshot(self.tmp, self.out), "difftool changed the repository or a reviewed file")
        proc.err = proc.stderr.decode(errors="replace")
        return proc

    def expected(self, *args, cwd=None, context=20):
        """The diff Git itself prints for the same comparison."""
        return self.git(
            "--literal-pathspecs", "diff", "--no-ext-diff", "--no-textconv", "--no-color",
            f"--unified={context}", *args, cwd=cwd,
        )

    def assert_same_as_git(self, proc, *args, cwd=None, context=20):
        want = self.expected(*args, cwd=cwd, context=context)
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertTrue(want, "the test expected Git to report a difference")
        self.assertEqual(proc.stdout, want)

    def assert_no_differences(self, proc):
        self.assertEqual(proc.returncode, 0, proc.err)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(NO_DIFFERENCES, proc.err)

    def assert_fails(self, proc, *fragments):
        self.assertEqual(proc.returncode, 1, proc.err)
        self.assertEqual(proc.stdout, b"")
        for fragment in fragments:
            self.assertIn(fragment, proc.err)

    def out_path(self, name="review.diff"):
        return os.path.join(self.out, name)

    def read(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    # -- 1-4: working tree and index ----------------------------------------

    def test_unstaged_edit(self):
        self.seed()
        self.write("f.txt", "two\n")
        self.assert_same_as_git(self.tool("f.txt"), "HEAD", "--", "f.txt")
        self.assert_same_as_git(self.tool("--unstaged", "f.txt"), "--", "f.txt")
        self.assert_no_differences(self.tool("--staged", "f.txt"))

    def test_staged_edit(self):
        self.seed()
        self.write("f.txt", "two\n")
        self.git("add", "f.txt")
        self.assert_same_as_git(self.tool("--staged", "f.txt"), "--cached", "HEAD", "--", "f.txt")
        self.assert_same_as_git(self.tool("f.txt"), "HEAD", "--", "f.txt")
        self.assert_no_differences(self.tool("--unstaged", "f.txt"))

    def test_staged_and_unstaged_edits_use_the_right_endpoints(self):
        self.seed(data="head\n")
        self.write("f.txt", "staged\n")
        self.git("add", "f.txt")
        self.write("f.txt", "working\n")

        staged = self.tool("--staged", "f.txt")
        self.assert_same_as_git(staged, "--cached", "HEAD", "--", "f.txt")
        self.assertIn(b"-head\n+staged\n", staged.stdout)

        unstaged = self.tool("--unstaged", "f.txt")
        self.assert_same_as_git(unstaged, "--", "f.txt")
        self.assertIn(b"-staged\n+working\n", unstaged.stdout)

        net = self.tool("f.txt")
        self.assert_same_as_git(net, "HEAD", "--", "f.txt")
        self.assertIn(b"-head\n+working\n", net.stdout)
        self.assertNotIn(b"staged", net.stdout)

    def test_staged_change_reversed_in_working_tree_is_no_net_change(self):
        self.seed(data="head\n")
        self.write("f.txt", "staged\n")
        self.git("add", "f.txt")
        self.write("f.txt", "head\n")
        self.assert_no_differences(self.tool("f.txt"))
        self.assertIn(b"-head\n+staged\n", self.tool("--staged", "f.txt").stdout)
        self.assertIn(b"-staged\n+head\n", self.tool("--unstaged", "f.txt").stdout)

    def test_stat_only_mismatch_is_no_difference_and_leaves_the_index_alone(self):
        self.seed()
        path = os.path.join(self.repo, "f.txt")
        later = os.stat(path).st_mtime + 100
        os.utime(path, (later, later))
        for args in (("f.txt",), ("--unstaged", "f.txt"), ("--staged", "f.txt")):
            with self.subTest(args=args):
                self.assert_no_differences(self.tool(*args))

    # -- 5-6: committed versions --------------------------------------------

    def test_commit_comparison_with_a_clean_working_tree(self):
        self.seed(data="one\n")
        first = self.sha("HEAD")
        self.write("f.txt", "two\n")
        self.commit("second")
        second = self.sha("HEAD")

        self.assert_no_differences(self.tool("f.txt"))
        proc = self.tool("--from", "HEAD~1", "--to", "HEAD", "f.txt")
        self.assert_same_as_git(proc, first, second, "--", "f.txt")
        self.assertIn(f"commit {first} (HEAD~1)", proc.err)
        self.assertIn(f"commit {second} (HEAD)", proc.err)
        # An abbreviated commit ID is resolved to the full one.
        self.assertIn(f"commit {first} ({first[:7]})", self.tool("--from", first[:7], "--to", "HEAD", "f.txt").err)
        self.assert_no_differences(self.tool("--from", "HEAD", "--to", "HEAD", "f.txt"))

    def test_merge_base_comparison_with_divergent_branches(self):
        self.seed(data="top\nmiddle\nbottom\n")
        base = self.sha("HEAD")
        self.git("checkout", "-q", "-b", "feature")
        self.write("f.txt", "top\nmiddle\nFEATURE\n")
        self.commit("feature work")
        self.git("checkout", "-q", "main")
        self.write("f.txt", "MAIN\nmiddle\nbottom\n")
        self.commit("main moved on")

        proc = self.tool("--merge-base", "main", "feature", "f.txt")
        self.assert_same_as_git(proc, base, self.sha("feature"), "--", "f.txt")
        self.assertIn(b"+FEATURE", proc.stdout)
        self.assertNotIn(b"MAIN", proc.stdout)
        self.assertIn(f"commit {base} (merge base of main", proc.err)
        # The direct comparison is a different question and also undoes main's change.
        self.assertIn(b"MAIN", self.tool("--from", "main", "--to", "feature", "f.txt").stdout)

    def test_merge_base_must_be_unique(self):
        self.seed()
        for branch, name in (("b1", "x1"), ("b2", "x2")):
            self.git("checkout", "-q", "-b", branch, "main")
            self.write(name, name)
            self.commit(branch)
        self.git("checkout", "-q", "-b", "m1", "b1")
        self.git("merge", "-q", "--no-ff", "-m", "m1", "b2")
        self.git("checkout", "-q", "-b", "m2", "b2")
        self.git("merge", "-q", "--no-ff", "-m", "m2", "b1")
        self.assert_fails(self.tool("--merge-base", "m1", "m2", "f.txt"), "2 merge bases")

    def test_merge_base_must_exist(self):
        self.seed()
        self.git("checkout", "-q", "--orphan", "lonely")
        self.write("f.txt", "unrelated\n")
        self.commit("unrelated history")
        self.assert_fails(self.tool("--merge-base", "main", "lonely", "f.txt"), "no merge base")

    # -- 7-8: how the path is given ------------------------------------------

    def test_relative_and_absolute_paths_inside_and_outside_the_repository(self):
        self.seed(rel="sub/f.txt")
        self.write("sub/f.txt", "two\n")
        want = self.expected("HEAD", "--", "sub/f.txt")
        absolute = os.path.join(self.repo, "sub", "f.txt")
        os.symlink(os.path.join(self.repo, "sub"), os.path.join(self.out, "shortcut"))
        cases = (
            (self.repo, "sub/f.txt"),
            (os.path.join(self.repo, "sub"), "f.txt"),
            (os.path.join(self.repo, "sub"), "../sub/f.txt"),
            (self.repo, absolute),
            (self.out, absolute),
            (self.tmp, "repo/sub/f.txt"),
            (self.out, "shortcut/f.txt"),
        )
        for cwd, arg in cases:
            with self.subTest(cwd=cwd, arg=arg):
                proc = self.tool(arg, cwd=cwd)
                self.assertEqual((proc.returncode, proc.stdout), (0, want), proc.err)
                self.assertIn("file:     sub/f.txt", proc.err)

    def test_spaces_unicode_and_pathspec_characters_are_literal(self):
        special = ["with space.md", "résumé – ñ.md", "*.md", "[ab].txt", ":(exclude)a.txt", ":!a.txt", "-dash.txt"]
        for name in special + ["a.txt", "b.md"]:
            self.write(name, f"old {name}\n")
        self.commit("names")
        for name in special + ["a.txt", "b.md"]:
            self.write(name, f"new {name}\n")
        for name in special:
            with self.subTest(name=name):
                proc = self.tool("--", name)
                self.assert_same_as_git(proc, "HEAD", "--", name)
                self.assertEqual(proc.stdout.count(b"diff --git"), 1)
                self.assertIn(f"+new {name}\n".encode(), proc.stdout)
                self.assertEqual(self.tool(os.path.join(self.repo, name), cwd=self.out).stdout, proc.stdout)

    # -- 9-11: what kind of file it is ---------------------------------------

    def test_deleted_tracked_file(self):
        self.seed(rel="gone/deep/f.txt")
        shutil.rmtree(os.path.join(self.repo, "gone"))
        absolute = os.path.join(self.repo, "gone", "deep", "f.txt")
        proc = self.tool(absolute, cwd=self.out)
        self.assert_same_as_git(proc, "HEAD", "--", "gone/deep/f.txt")
        self.assertIn(b"deleted file mode", proc.stdout)
        self.assert_same_as_git(self.tool("--unstaged", "gone/deep/f.txt"), "--", "gone/deep/f.txt")

    def test_file_staged_for_removal(self):
        self.seed()
        self.git("rm", "-q", "f.txt")
        self.assertIn(b"deleted file mode", self.tool("f.txt").stdout)
        self.assert_same_as_git(self.tool("--staged", "f.txt"), "--cached", "HEAD", "--", "f.txt")
        self.assert_fails(self.tool("--unstaged", "f.txt"), "not in the index")

    def test_newly_staged_file(self):
        self.seed()
        self.write("new.txt", "fresh\n")
        self.git("add", "new.txt")
        for args in (("new.txt",), ("--staged", "new.txt")):
            proc = self.tool(*args)
            self.assertEqual(proc.returncode, 0, proc.err)
            self.assertIn(b"new file mode", proc.stdout)
            self.assertIn(b"+fresh\n", proc.stdout)
        self.assert_no_differences(self.tool("--unstaged", "new.txt"))

    def test_untracked_file_is_rejected_and_never_staged(self):
        self.seed()
        self.write("loose.txt", "never added\n")
        for args in (("loose.txt",), ("--staged", "loose.txt"), ("--unstaged", "loose.txt")):
            with self.subTest(args=args):
                self.assert_fails(self.tool(*args, "-o", self.out_path()), "untracked", "needs a Git version")
        self.assertEqual(self.git("ls-files", "--", "loose.txt"), b"")
        self.assertFalse(os.path.lexists(self.out_path()))

    def test_path_that_exists_nowhere(self):
        self.seed()
        self.assert_fails(self.tool("nowhere.txt"), "was not found")
        self.assert_fails(self.tool("--from", "HEAD", "--to", "HEAD", "nowhere.txt"), "in neither commit")

    def test_historical_path_absent_from_the_current_checkout(self):
        self.seed(rel="old.txt", data="history\n")
        self.git("rm", "-q", "old.txt")
        self.write("f.txt", "current\n")
        self.commit("drop old.txt")
        proc = self.tool("--from", "HEAD~1", "--to", "HEAD", "old.txt")
        self.assert_same_as_git(proc, self.sha("HEAD~1"), self.sha("HEAD"), "--", "old.txt")
        self.assertIn(b"-history\n", proc.stdout)
        self.assertIn(b"+history\n", self.tool("--from", "HEAD", "--to", "HEAD~1", os.path.join(self.repo, "old.txt"), cwd=self.out).stdout)
        self.assert_fails(self.tool("old.txt"), "was not found")

    def test_tracked_symlink_is_compared_as_the_link_itself(self):
        self.write("target.txt", "target content\n")
        self.write("other.txt", "other content\n")
        link = os.path.join(self.repo, "link.txt")
        os.symlink("target.txt", link)
        self.commit("link")
        os.remove(link)
        os.symlink("other.txt", link)
        self.write("target.txt", "target content changed\n")

        proc = self.tool(link, cwd=self.out)
        self.assert_same_as_git(proc, "HEAD", "--", "link.txt")
        self.assertIn(b"120000", proc.stdout)
        self.assertIn(b"-target.txt", proc.stdout)
        self.assertIn(b"+other.txt", proc.stdout)
        self.assertNotIn(b"content", proc.stdout)
        self.assertIn("tracked symlink", proc.err)

    # -- 12: bytes ------------------------------------------------------------

    def test_binary_difference_is_reported_as_binary(self):
        self.seed(rel="blob.bin", data=b"\x00\x01\x02 first")
        self.write("blob.bin", b"\x00\x01\x02 second")
        proc = self.tool("blob.bin")
        self.assert_same_as_git(proc, "HEAD", "--", "blob.bin")
        self.assertIn(b"Binary files", proc.stdout)
        self.assertIn("binary difference", proc.err)
        self.assertNotIn(NO_DIFFERENCES, proc.err)

        saved = self.tool("blob.bin", "-o", self.out_path())
        self.assertIn("binary difference", saved.err)
        self.assertEqual(self.read(self.out_path()), proc.stdout)

    def test_diff_bytes_are_not_decoded_or_altered(self):
        self.seed(rel="latin1.txt", data=b"caf\xe9\r\nplain\n")
        self.write("latin1.txt", b"caf\xe8\r\nplain\n")
        proc = self.tool("latin1.txt")
        self.assert_same_as_git(proc, "HEAD", "--", "latin1.txt")
        self.assertIn(b"+caf\xe8\r\n", proc.stdout)
        self.assertNotIn("binary difference", proc.err)

    # -- 13-14: the -o destination --------------------------------------------

    def test_no_differences_never_creates_or_replaces_the_output_file(self):
        self.seed()
        self.assert_no_differences(self.tool("f.txt", "-o", self.out_path()))
        self.assertFalse(os.path.lexists(self.out_path()))
        self.write(self.out_path(), "earlier review\n")
        for extra in ((), ("--force",)):
            self.assert_no_differences(self.tool("f.txt", "-o", self.out_path(), *extra))
            self.assertEqual(self.read(self.out_path()), b"earlier review\n")

    def test_output_file_holds_only_the_patch(self):
        self.seed()
        self.write("f.txt", "two\n")
        proc = self.tool(os.path.join(self.repo, "f.txt"), "-o", "review.diff", cwd=self.out)
        self.assertEqual((proc.returncode, proc.stdout), (0, b""), proc.err)
        self.assertEqual(self.read(self.out_path()), self.expected("HEAD", "--", "f.txt"))
        self.assertIn(f"output:   {self.out_path()}", proc.err)
        self.assertEqual(os.listdir(self.out), ["review.diff"])

    def test_existing_output_needs_force(self):
        self.seed()
        self.write("f.txt", "two\n")
        self.write(self.out_path(), "keep me\n")
        self.assert_fails(self.tool("f.txt", "-o", self.out_path()), "already exists", "--force")
        self.assertEqual(self.read(self.out_path()), b"keep me\n")
        self.assertEqual(self.tool("f.txt", "-o", self.out_path(), "--force").returncode, 0)
        self.assertEqual(self.read(self.out_path()), self.expected("HEAD", "--", "f.txt"))
        self.assertEqual(os.listdir(self.out), ["review.diff"])

    def test_output_symlink_is_never_followed(self):
        self.seed()
        self.write("f.txt", "two\n")
        victim = self.write(os.path.join(self.out, "victim.txt"), "do not touch\n")
        os.symlink(victim, self.out_path())
        os.symlink(os.path.join(self.out, "not-there"), self.out_path("dangling.diff"))

        self.assert_fails(self.tool("f.txt", "-o", self.out_path()), "already exists")
        self.assert_fails(self.tool("f.txt", "-o", self.out_path("dangling.diff")), "already exists")
        self.assertTrue(os.path.islink(self.out_path()))
        self.assertFalse(os.path.lexists(os.path.join(self.out, "not-there")))

        self.assertEqual(self.tool("f.txt", "-o", self.out_path(), "--force").returncode, 0)
        self.assertFalse(os.path.islink(self.out_path()))
        self.assertEqual(self.read(self.out_path()), self.expected("HEAD", "--", "f.txt"))
        self.assertEqual(self.read(victim), b"do not touch\n")

    def test_output_can_never_be_the_reviewed_file_or_an_alias_of_it(self):
        self.seed()
        self.write("f.txt", "two\n")
        reviewed = os.path.join(self.repo, "f.txt")
        os.link(reviewed, self.out_path("hardlink"))
        os.symlink(reviewed, self.out_path("symlink"))
        for dest in (reviewed, "f.txt", "./sub/../f.txt", self.out_path("hardlink"), self.out_path("symlink")):
            for extra in ((), ("--force",)):
                with self.subTest(dest=dest, extra=extra):
                    os.makedirs(os.path.join(self.repo, "sub"), exist_ok=True)
                    self.assert_fails(self.tool("f.txt", "-o", dest, *extra), "refusing to write")
        self.assertEqual(self.read(reviewed), b"two\n")
        # A deleted reviewed file's own path is still refused.
        os.remove(reviewed)
        self.assert_fails(self.tool("f.txt", "-o", reviewed), "the file being reviewed")

    def test_output_can_never_be_git_administrative_data(self):
        self.seed()
        self.write("f.txt", "two\n")
        worktree = os.path.join(self.tmp, "wt")
        self.git("worktree", "add", "-q", "-b", "side", worktree)
        self.write("f.txt", "side\n", repo=worktree)
        git_dir = os.path.join(self.repo, ".git")
        for cwd, dest in (
            (self.repo, os.path.join(git_dir, "review.diff")),
            (self.repo, os.path.join(git_dir, "index")),
            (self.repo, ".git/hooks/review.diff"),
            (worktree, os.path.join(worktree, ".git")),
            (worktree, os.path.join(git_dir, "worktrees", "wt", "review.diff")),
        ):
            with self.subTest(dest=dest):
                self.assert_fails(self.tool("f.txt", "-o", dest, "--force", cwd=cwd), "refusing to write")

    def test_output_directory_must_exist_and_output_must_be_a_file(self):
        self.seed()
        self.write("f.txt", "two\n")
        self.assert_fails(self.tool("f.txt", "-o", os.path.join(self.out, "missing", "r.diff")), "does not exist")
        self.assert_fails(self.tool("f.txt", "-o", self.out, "--force"), "directory")
        self.assertEqual(os.listdir(self.out), [])

    # -- 15: failures ----------------------------------------------------------

    def test_invalid_reference_writes_nothing(self):
        self.seed()
        self.write("f.txt", "two\n")
        for args in (("--from", "no-such-ref", "--to", "HEAD"), ("--from", "HEAD", "--to", "no-such-ref"),
                     ("--merge-base", "no-such-ref", "HEAD"), ("--from", "HEAD:f.txt", "--to", "HEAD")):
            with self.subTest(args=args):
                self.assert_fails(self.tool(*args, "f.txt", "-o", self.out_path()), "does not resolve to a commit")
        self.assertEqual(os.listdir(self.out), [])

    def test_usage_errors_exit_2(self):
        for args in (
            [],
            ["a.txt", "b.txt"],
            ["--from", "HEAD", "f.txt"],
            ["--to", "HEAD", "f.txt"],
            ["--staged", "--unstaged", "f.txt"],
            ["--staged", "--from", "HEAD", "--to", "HEAD", "f.txt"],
            ["--unstaged", "--merge-base", "HEAD", "HEAD", "f.txt"],
            ["--from", "HEAD", "--to", "HEAD", "--merge-base", "HEAD", "HEAD", "f.txt"],
            ["--merge-base", "HEAD", "f.txt"],
            ["--context", "-1", "f.txt"],
            ["--context", "many", "f.txt"],
            ["--force", "f.txt"],
            ["--no-such-option", "f.txt"],
            [""],
        ):
            with self.subTest(args=args):
                proc = self.tool(*args)
                self.assertEqual((proc.returncode, proc.stdout), (2, b""), proc.err)
                self.assertIn("usage:", proc.err)

    def test_git_failure_leaves_no_partial_output(self):
        self.seed()
        self.write("f.txt", "two\n")
        fake_bin = os.path.join(self.out, "bin")
        os.makedirs(fake_bin)
        fake_git = os.path.join(fake_bin, "git")
        with open(fake_git, "w") as handle:
            handle.write(
                "#!/bin/sh\n"
                'for arg in "$@"; do\n'
                '  if [ "$arg" = diff ]; then echo "fatal: simulated diff failure" >&2; exit 128; fi\n'
                "done\n"
                f'exec "{REAL_GIT}" "$@"\n'
            )
        os.chmod(fake_git, 0o755)
        env = dict(self.env, PATH=fake_bin + os.pathsep + self.env["PATH"])

        self.assert_fails(self.tool("f.txt", env=env), "simulated diff failure")
        self.assert_fails(self.tool("f.txt", "-o", self.out_path(), env=env), "simulated diff failure")
        self.assertFalse(os.path.lexists(self.out_path()))
        self.write(self.out_path(), "keep me\n")
        self.assert_fails(self.tool("f.txt", "-o", self.out_path(), "--force", env=env), "simulated diff failure")
        self.assertEqual(self.read(self.out_path()), b"keep me\n")
        self.assertEqual(sorted(os.listdir(self.out)), ["bin", "review.diff"])

    def test_paths_that_are_not_a_tracked_file_in_a_repository(self):
        self.seed(rel="sub/f.txt")
        outside = self.write(os.path.join(self.out, "plain.txt"), "no repository here\n")
        self.assert_fails(self.tool(outside), "no Git working tree")
        self.assert_fails(self.tool("sub"), "directory")
        self.assert_fails(self.tool("."), "directory")
        self.assert_fails(self.tool(os.path.join(self.repo, ".git", "config")), "no Git working tree")

    def test_repository_without_commits(self):
        self.write("f.txt", "one\n")
        self.git("add", "f.txt")
        self.assert_fails(self.tool("f.txt"), "HEAD does not resolve")
        self.assert_fails(self.tool("--staged", "f.txt"), "HEAD does not resolve")
        self.assert_no_differences(self.tool("--unstaged", "f.txt"))

    # -- 16 and the rest: summary, context, worktrees, environment --------------

    def test_diff_goes_to_stdout_and_the_summary_to_stderr(self):
        self.seed()
        head = self.sha("HEAD")
        self.write("f.txt", "two\n")
        proc = self.tool("f.txt")
        self.assert_same_as_git(proc, "HEAD", "--", "f.txt")
        for fragment in (
            f"worktree: {self.repo}",
            "file:     f.txt",
            "working tree vs HEAD",
            f"from:     commit {head} (HEAD)",
            "to:       working tree (mutable, not identified by a commit hash)",
        ):
            self.assertIn(fragment, proc.err)
        self.assertNotIn("diff --git", proc.err)
        self.assertNotIn("+two", proc.err)

        self.git("add", "f.txt")
        self.assertIn("to:       index (mutable, not identified by a commit hash)", self.tool("--staged", "f.txt").err)
        unstaged = self.tool("--unstaged", "f.txt").err
        self.assertIn("from:     index (mutable", unstaged)
        self.assertIn("to:       working tree (mutable", unstaged)

    def test_context_defaults_to_20_and_can_be_changed(self):
        lines = [f"line {n}\n" for n in range(1, 101)]
        self.seed(data="".join(lines))
        lines[49] = "changed\n"
        self.write("f.txt", "".join(lines))
        self.assertIn(b"@@ -30,41 +30,41 @@", self.tool("f.txt").stdout)
        for context in (0, 3, 40):
            with self.subTest(context=context):
                proc = self.tool("--context", str(context), "f.txt")
                self.assert_same_as_git(proc, "HEAD", "--", "f.txt", context=context)

    def test_linked_worktree(self):
        self.seed(data="one\n")
        worktree = os.path.join(self.tmp, "wt")
        self.git("worktree", "add", "-q", "-b", "feature", worktree)
        self.assertTrue(os.path.isfile(os.path.join(worktree, ".git")))
        self.write("f.txt", "main checkout edit\n")
        self.write("f.txt", "committed on feature\n", repo=worktree)
        self.commit("feature commit", cwd=worktree)
        self.write("f.txt", "uncommitted in worktree\n", repo=worktree)

        proc = self.tool(os.path.join(worktree, "f.txt"), cwd=self.out)
        self.assert_same_as_git(proc, "HEAD", "--", "f.txt", cwd=worktree)
        self.assertIn(b"-committed on feature\n+uncommitted in worktree\n", proc.stdout)
        self.assertIn(f"worktree: {worktree}", proc.err)
        self.assertIn(f"commit {self.sha('HEAD', cwd=worktree)} (HEAD)", proc.err)

        merged = self.tool("--merge-base", "main", "HEAD", "f.txt", cwd=worktree)
        self.assertIn(b"-one\n+committed on feature\n", merged.stdout)
        # The main checkout's own uncommitted edit is a separate comparison.
        self.assertIn(b"-one\n+main checkout edit\n", self.tool("f.txt").stdout)

    def test_git_environment_cannot_redirect_the_comparison(self):
        self.seed()
        self.write("f.txt", "two\n")
        other = os.path.join(self.tmp, "other")
        self.git("init", "-q", "-b", "main", other, cwd=self.tmp)
        self.write("f.txt", "other repository\n", repo=other)
        self.commit("other", cwd=other)
        env = dict(self.env, GIT_DIR=os.path.join(other, ".git"), GIT_WORK_TREE=other, GIT_EXTERNAL_DIFF="false")
        proc = self.tool("f.txt", env=env)
        self.assertEqual((proc.returncode, proc.stdout), (0, self.expected("HEAD", "--", "f.txt")), proc.err)


if __name__ == "__main__":
    unittest.main()

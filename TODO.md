# TODO

Pending work for the tools in this repo. One entry per task, newest first.
Format: `- [ ] YYYY-MM-DD <tool> — <what to do>`, followed by indented detail.

## Tasks

- [ ] 2026-08-02 `check-git-repos` — ignore all occurrences of `CHECKPOINT.md` in **any** repo, not just this one.

  An untracked `CHECKPOINT.md` must never contribute to a repo's status. A repo whose
  only untracked file is `CHECKPOINT.md` should report clean instead of `UNTRACKED`.
  This applies globally to every repo the scan walks — it is not a per-repo opt-in.

  Why: `CHECKPOINT.md` is a transient AI planning file (see
  `~/ai/directives/project-planning-with-ai.md`) that is deliberately left uncommitted
  while work is in flight, so it is noise in `check-git-repos` output.

  Notes for whoever picks this up:
  - The existing ignore mechanism cannot express this. `~/.config/check-git-repos-source/ignore.txt`
    is **path**-based and skips whole repos (`loadIgnore`, `check-git-repos-source/main.go:296`,
    plus `--ignore-prefix`); `filterParentIgnored` only handles repos gitignored by an
    enclosing repo. This needs a new per-**filename** exclusion.
  - Apply it in the `git status --porcelain` parse where `hasUntracked` is set
    (`check-git-repos-source/main.go:355-378`).
  - Decide whether the excluded name is hardcoded or configurable. Hardcoding
    `CHECKPOINT.md` is acceptable and simpler.
  - Current release is `check-git-repos-v1.9.0`. This is new backward-compatible
    behaviour, so tag `check-git-repos-v1.10.0`.
  - Per `CLAUDE.md`: `go build .` and exercise the change before committing; keep
    `go.mod` at the installed Go `MAJOR.MINOR`; update `check-git-repos-source/README.md`,
    `README.md`, and `RUNBOOK.md` in the same commit. After tagging, append the sync and
    binary-install entries to `~/todo/mac/TODO.md` and `~/todo/rpi/TODO.md`.

package main

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// version is overridden at build time via -ldflags "-X main.version=...".
var version = "dev"

// defaultLockStaleAfter is how old a *.lock file must be before it counts as
// stale. Git's own lock files are held for well under a second in normal use,
// so five minutes clears any live operation by a wide margin while still
// catching locks orphaned by a crashed or killed git process.
const defaultLockStaleAfter = 5 * time.Minute

// parseLockStaleAfter parses a --lock-stale-after value, e.g. "5m", "90s", "1h".
// Zero disables the age test entirely, so every *.lock file counts as stale.
func parseLockStaleAfter(raw string) (time.Duration, error) {
	d, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("invalid --lock-stale-after value %q: %w (expected a duration such as 5m, 90s or 1h)", raw, err)
	}
	if d < 0 {
		return 0, fmt.Errorf("invalid --lock-stale-after value %q: duration must not be negative", raw)
	}
	return d, nil
}

// defaultStashStaleAfter is how old a stash must be before it is reported as
// STALE rather than STASH. Fourteen days is deliberately longer than a working
// session: a stash made this morning is normal work in progress, while one that
// has survived a fortnight is content sitting in no commit on no branch, which
// nothing else in this tool would ever surface.
const defaultStashStaleAfter = 14 * 24 * time.Hour

// parseStashStaleAfter parses a --stash-stale-after value. It accepts Go's own
// duration units plus 'd' (days) and 'w' (weeks), because the useful thresholds
// here are measured in days and time.ParseDuration stops at hours — "14d" is a
// natural thing to type and an error Go would otherwise reject.
// Zero disables the age test, so every stash counts as stale.
func parseStashStaleAfter(raw string) (time.Duration, error) {
	fail := func(reason string) (time.Duration, error) {
		return 0, fmt.Errorf("invalid --stash-stale-after value %q: %s (expected a duration such as 14d, 2w, 36h or 90m)", raw, reason)
	}
	s := strings.TrimSpace(raw)
	if s == "" {
		return fail("empty")
	}
	// Translate a trailing d/w into hours, then let time.ParseDuration do the rest.
	if unit := s[len(s)-1]; unit == 'd' || unit == 'w' {
		n, err := strconv.ParseFloat(s[:len(s)-1], 64)
		if err != nil {
			return fail("not a number before the unit")
		}
		hours := n * 24
		if unit == 'w' {
			hours *= 7
		}
		s = strconv.FormatFloat(hours, 'f', -1, 64) + "h"
	}
	d, err := time.ParseDuration(s)
	if err != nil {
		return fail(err.Error())
	}
	if d < 0 {
		return fail("duration must not be negative")
	}
	return d, nil
}

// defaultStaleWorktreeDays is how many days old a linked git worktree may be
// before --worktree reports STALE alongside WT. Three days comfortably
// covers a normal ticket's implementation span; an ai-wt/<ISSUE> worktree
// still standing past that has usually just been forgotten rather than
// genuinely still in use.
const defaultStaleWorktreeDays = 3

// parseStaleDays parses a --stale-days value: a non-negative whole number of
// days. Zero disables the age test, so any worktree found counts as stale.
func parseStaleDays(raw string) (int, error) {
	n, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("invalid --stale-days value %q: expected a whole number of days", raw)
	}
	if n < 0 {
		return 0, fmt.Errorf("invalid --stale-days value %q: must not be negative", raw)
	}
	return n, nil
}

// worktreeState reports whether a repository has any linked git worktree
// beyond its own primary working tree, and whether the oldest of them is
// stale.
//
// A linked worktree's age is taken from its own directory's modification
// time. In ordinary use that mtime is set when the worktree is created and
// changes again only if a top-level entry inside it is added or removed —
// editing files already present, or committing, does not touch it — so it
// stands in for "when was this worktree created" without any extra git
// plumbing (git records no creation timestamp for a worktree itself).
func worktreeState(repo string, disableLock bool, staleAfter time.Duration) (has, stale bool) {
	out, err := exec.Command("git", gitArgs(repo, disableLock, "worktree", "list", "--porcelain")...).Output()
	if err != nil {
		return false, false
	}
	cutoff := time.Now().Add(-staleAfter)
	for _, block := range strings.Split(string(out), "\n\n") {
		line, _, _ := strings.Cut(block, "\n")
		path, ok := strings.CutPrefix(line, "worktree ")
		if !ok {
			continue
		}
		if filepath.Clean(path) == filepath.Clean(repo) {
			continue // the primary working tree itself, not a linked worktree
		}
		has = true
		info, statErr := os.Stat(path)
		if statErr != nil {
			// Can no longer be statted (e.g. removed since 'git worktree list'
			// ran) — its age can't be measured, so don't silently miss it.
			stale = true
			continue
		}
		if staleAfter == 0 || info.ModTime().Before(cutoff) {
			stale = true
		}
	}
	return has, stale
}

// stashState reports whether a repository holds any stashes, and whether the
// oldest of them is stale.
//
// Stashes are the one state this tool reports that `git status` cannot see: a
// repo holding a six-month-old stash presents a perfectly clean working tree, so
// nothing ever surfaces the content sitting in no commit on no branch. That is
// exactly how stashes months old survive unnoticed.
//
// refs/stash lives in the COMMON git dir, so stashes are per-repository and
// shared across linked worktrees — a stash made inside ai-wt/<ISSUE>/ belongs to
// the repo as a whole and is reported once, here.
//
// A repo that has never stashed has no refs/stash at all, so this costs one
// cheap git call that returns immediately.
func stashState(repo string, disableLock bool, staleAfter time.Duration) (has, stale bool) {
	out, err := exec.Command("git", gitArgs(repo, disableLock, "stash", "list", "--format=%ct")...).Output()
	if err != nil {
		return false, false
	}
	cutoff := time.Now().Add(-staleAfter)
	for _, line := range strings.Split(strings.TrimSpace(string(out)), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		has = true
		secs, convErr := strconv.ParseInt(line, 10, 64)
		if convErr != nil {
			// An unparseable timestamp must not silently downgrade the finding:
			// the stash is real either way, so treat it as the urgent case.
			stale = true
			continue
		}
		if staleAfter == 0 || time.Unix(secs, 0).Before(cutoff) {
			stale = true
		}
	}
	return has, stale
}

type result struct {
	display string
	status  string
}

type spinner struct {
	mu   sync.Mutex
	msg  string
	done chan struct{}
	wg   sync.WaitGroup
}

func newSpinner(msg string) *spinner {
	s := &spinner{msg: msg, done: make(chan struct{})}
	s.wg.Add(1)
	go func() {
		defer s.wg.Done()
		frames := []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}
		i := 0
		for {
			select {
			case <-s.done:
				fmt.Fprint(os.Stderr, "\r\033[K")
				return
			default:
				s.mu.Lock()
				m := s.msg
				s.mu.Unlock()
				fmt.Fprintf(os.Stderr, "\r%s %s", frames[i%len(frames)], m)
				i++
				time.Sleep(80 * time.Millisecond)
			}
		}
	}()
	return s
}

func (s *spinner) setMsg(msg string) {
	s.mu.Lock()
	s.msg = msg
	s.mu.Unlock()
}

func (s *spinner) stop() {
	close(s.done)
	s.wg.Wait()
}

func isTerminal(f *os.File) bool {
	fi, err := f.Stat()
	if err != nil {
		return false
	}
	return fi.Mode()&os.ModeCharDevice != 0
}

func main() {
	var batchMode bool
	var checkpointOnly bool
	var disableLock bool
	var ignorePrefix bool
	var removeLocks bool
	var worktree bool
	lockStaleAfter := defaultLockStaleAfter
	stashStaleAfter := defaultStashStaleAfter
	staleWorktreeAfter := time.Duration(defaultStaleWorktreeDays) * 24 * time.Hour
	args := os.Args[1:]
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if raw, ok := strings.CutPrefix(arg, "--stash-stale-after="); ok {
			d, err := parseStashStaleAfter(raw)
			if err != nil {
				fmt.Fprintln(os.Stderr, "error:", err)
				os.Exit(1)
			}
			stashStaleAfter = d
			continue
		}
		if raw, ok := strings.CutPrefix(arg, "--lock-stale-after="); ok {
			d, err := parseLockStaleAfter(raw)
			if err != nil {
				fmt.Fprintln(os.Stderr, "error:", err)
				os.Exit(1)
			}
			lockStaleAfter = d
			continue
		}
		if raw, ok := strings.CutPrefix(arg, "--stale-days="); ok {
			n, err := parseStaleDays(raw)
			if err != nil {
				fmt.Fprintln(os.Stderr, "error:", err)
				os.Exit(1)
			}
			staleWorktreeAfter = time.Duration(n) * 24 * time.Hour
			continue
		}
		switch arg {
		case "--version", "-v":
			fmt.Println("check-git-repos v" + version)
			os.Exit(0)
		case "--help", "-h":
			fmt.Print("Usage: check-git-repos [--version] [--help] [--batch-mode] [--checkpoint] [--disable-lock] [--ignore-prefix] [--remove-locks] [--lock-stale-after DURATION]\n                          [--stash-stale-after DURATION] [--worktree] [--stale-days N]\n\n" +
				"Scans all git repositories under $HOME (and any paths listed in\n" +
				"$CHECK_GIT_REPOS) and reports any that are ahead, behind, diverged\n" +
				"from their upstream, or have a dirty working tree.\n\n" +
				"Options:\n" +
				"  --version        Print version and exit\n" +
				"  --help           Print this help and exit\n" +
				"  --batch-mode     Suppress the progress spinner (for systemd/cron)\n" +
				"  --checkpoint     Report only repositories containing a CHECKPOINT.md,\n" +
				"                   and print nothing else. One line per matching repo,\n" +
				"                   no summary, no count, and no output at all when none\n" +
				"                   are found — silence means no unfinished AI work is\n" +
				"                   outstanding. Skips 'git fetch' and every other check,\n" +
				"                   so it finishes in seconds where a full scan takes\n" +
				"                   minutes. Each repository is searched in full rather\n" +
				"                   than at its root only: in a tracking repository\n" +
				"                   (~/admin, /opt/containers) a project's CHECKPOINT.md\n" +
				"                   belongs in that project's own subdirectory.\n" +
				"                   Takes precedence over --disable-lock, --remove-locks\n" +
				"                   and --lock-stale-after, which have nothing to do in\n" +
				"                   this mode.\n" +
				"  --disable-lock   Avoid acquiring git lock files. Skips 'git fetch'\n" +
				"                   entirely and passes --no-optional-locks to all git\n" +
				"                   invocations. Use this when another git process (an\n" +
				"                   IDE, another scan) may be running concurrently.\n" +
				"                   WARNING: AHEAD/BEHIND results reflect whatever the\n" +
				"                   last fetch saw — they will be stale relative to the\n" +
				"                   remote. Dirty-tree detection is unaffected.\n" +
				"  --ignore-prefix  Treat each entry in the ignore file as a plain text\n" +
				"                   path-prefix instead of an exact path or path-component\n" +
				"                   prefix. With this flag, an ignore entry of\n" +
				"                   ~/Projects/workspaces/DOSD also skips repos under\n" +
				"                   ~/Projects/workspaces/DOSD-5844, DOSD-5904, etc.\n" +
				"  --remove-locks   Remove stale *.lock files from every discovered\n" +
				"                   repository's .git/ directory before running the check.\n" +
				"                   Prints each removed path. Only lock files older than\n" +
				"                   --lock-stale-after are removed, so a lock held by a\n" +
				"                   live git process is left alone.\n" +
				"  --stash-stale-after DURATION\n" +
				"                   How old a stash must be to report STALE rather than\n" +
				"                   STASH. Default 14d. Accepts d and w as well as Go\n" +
				"                   units (14d, 2w, 36h, 90m). 0 treats every stash as\n" +
				"                   stale.\n" +
				"  --lock-stale-after DURATION\n" +
				"                   How old a *.lock file must be before it is treated as\n" +
				"                   stale, for both the LOCKED status and --remove-locks.\n" +
				"                   Default 5m. Accepts any Go duration (90s, 5m, 1h).\n" +
				"                   Set to 0 to disable the age test and treat every\n" +
				"                   *.lock file as stale (the pre-v1.11.0 behaviour).\n" +
				"  --worktree       Check each repository for a linked git worktree\n" +
				"                   (e.g. an ai-wt/<ISSUE> AI worktree) and report WT when\n" +
				"                   one is present. A worktree older than --stale-days\n" +
				"                   additionally reports STALE alongside WT.\n" +
				"  --stale-days N   How many days old a linked worktree found by\n" +
				"                   --worktree may be before it is also reported STALE.\n" +
				"                   Default 3. A whole number of days; 0 treats every\n" +
				"                   worktree found as stale. Has no effect without\n" +
				"                   --worktree.\n\n" +
				"Environment:\n" +
				"  CHECK_GIT_REPOS  Colon-separated list of additional directory paths to\n" +
				"                   scan for git repositories, e.g.:\n" +
				"                     export CHECK_GIT_REPOS=/srv/repos:/opt/src\n" +
				"                   ~ is expanded. Every listed path must exist and be a\n" +
				"                   directory — the program exits with an error otherwise.\n" +
				"                   $HOME is always scanned regardless of this variable.\n" +
				"                   Repos found in extra paths are displayed using their\n" +
				"                   full absolute path.\n\n" +
				"Statuses reported:\n" +
				"  AHEAD            Local commits not yet pushed\n" +
				"  BEHIND           Remote commits not yet pulled\n" +
				"  STAGED           Changes indexed but not committed\n" +
				"  UNSTAGED         Tracked files with uncommitted edits\n" +
				"  UNTRACKED        Files not yet added to git\n" +
				"  CHECKPOINT       An untracked CHECKPOINT.md is present, meaning AI\n" +
				"                   work was started here and never finished. Reported\n" +
				"                   separately from UNTRACKED because CHECKPOINT.md is\n" +
				"                   never meant to be committed. A repo whose only\n" +
				"                   untracked file is CHECKPOINT.md reports CHECKPOINT\n" +
				"                   alone, not UNTRACKED. Use --checkpoint to search for\n" +
				"                   these and nothing else.\n" +
				"  LOCKED           Stale *.lock files present under .git/ (older than\n" +
				"                   --lock-stale-after)\n" +
				"  STASH            Stashes present, none older than --stash-stale-after.\n" +
				"                   Normal work in progress, but reported because a stash\n" +
				"                   is invisible to 'git status': a repo holding one shows\n" +
				"                   a clean working tree while its content sits in no\n" +
				"                   commit on no branch.\n" +
				"  STALE            At least one stash is older than --stash-stale-after\n" +
				"                   (default 14d), so it has outlived the session that\n" +
				"                   made it. Reported instead of STASH, never alongside\n" +
				"                   it, so the actionable finding is not buried. Also\n" +
				"                   reported (only with --worktree) alongside WT when a\n" +
				"                   linked worktree is older than --stale-days.\n" +
				"  WT               (--worktree only) A linked git worktree is present\n" +
				"                   for this repository — e.g. an ai-wt/<ISSUE> AI\n" +
				"                   worktree still checked out.\n\n" +
				"Ignore file: ~/.config/check-git-repos-source/ignore.txt\n" +
				"  One path per line (~ expanded). Repos under those paths are skipped.\n" +
				"  Lines beginning with # are treated as comments.\n")
			os.Exit(0)
		case "--batch-mode":
			batchMode = true
		case "--checkpoint":
			checkpointOnly = true
		case "--disable-lock":
			disableLock = true
		case "--ignore-prefix":
			ignorePrefix = true
		case "--remove-locks":
			removeLocks = true
		case "--worktree":
			worktree = true
		case "--stale-days":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "error: --stale-days requires a number of days, e.g. --stale-days 5")
				os.Exit(1)
			}
			n, err := parseStaleDays(args[i])
			if err != nil {
				fmt.Fprintln(os.Stderr, "error:", err)
				os.Exit(1)
			}
			staleWorktreeAfter = time.Duration(n) * 24 * time.Hour
		case "--lock-stale-after":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "error: --lock-stale-after requires a duration argument, e.g. --lock-stale-after 5m")
				os.Exit(1)
			}
			d, err := parseLockStaleAfter(args[i])
			if err != nil {
				fmt.Fprintln(os.Stderr, "error:", err)
				os.Exit(1)
			}
			lockStaleAfter = d
		case "--stash-stale-after":
			i++
			if i >= len(args) {
				fmt.Fprintln(os.Stderr, "error: --stash-stale-after requires a duration argument, e.g. --stash-stale-after 14d")
				os.Exit(1)
			}
			d, err := parseStashStaleAfter(args[i])
			if err != nil {
				fmt.Fprintln(os.Stderr, "error:", err)
				os.Exit(1)
			}
			stashStaleAfter = d
		default:
			fmt.Fprintf(os.Stderr, "unknown flag: %s\nRun with --help for usage.\n", arg)
			os.Exit(1)
		}
	}

	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintln(os.Stderr, "error: cannot determine home directory:", err)
		os.Exit(1)
	}

	showSpinner := !batchMode && isTerminal(os.Stderr)

	ignorePaths := loadIgnore(home)

	extraRoots, err := parseExtraRoots(home)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
	roots := append([]string{home}, extraRoots...)

	var spin *spinner
	if showSpinner {
		spin = newSpinner("scanning for repositories…")
	}

	repoSet := make(map[string]struct{})
	var repos []string
	for _, root := range roots {
		walkErr := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
			if err != nil {
				return filepath.SkipDir
			}
			if d.IsDir() {
				for _, ig := range ignorePaths {
					if ignorePrefix {
						if strings.HasPrefix(path, ig) {
							return filepath.SkipDir
						}
					} else if path == ig || strings.HasPrefix(path, ig+string(filepath.Separator)) {
						return filepath.SkipDir
					}
				}
				if d.Name() == ".git" {
					repoPath := filepath.Dir(path)
					if _, seen := repoSet[repoPath]; !seen {
						repoSet[repoPath] = struct{}{}
						repos = append(repos, repoPath)
					}
					return filepath.SkipDir
				}
			}
			return nil
		})
		if walkErr != nil {
			if spin != nil {
				spin.stop()
			}
			fmt.Fprintf(os.Stderr, "error walking %s: %v\n", root, walkErr)
			os.Exit(1)
		}
	}

	repos = filterParentIgnored(repos, repoSet)

	if checkpointOnly {
		if spin != nil {
			spin.setMsg(fmt.Sprintf("searching %d repositories for CHECKPOINT.md…", len(repos)))
		}
		found := findCheckpoints(repos, repoSet, home)
		if spin != nil {
			spin.stop()
		}
		// Deliberately silent when nothing is found: no summary, no count, no
		// "none found" line. This mode exists to be run habitually, so its
		// entire signal is whether it printed anything at all.
		for _, line := range found {
			fmt.Println(line + " is CHECKPOINT")
		}
		return
	}

	if removeLocks {
		if spin != nil {
			spin.stop()
			spin = nil
		}
		removed := removeStaleLocks(repos, home, lockStaleAfter)
		if len(removed) == 0 {
			fmt.Println("no stale locks found")
		} else {
			for _, p := range removed {
				fmt.Println("removed lock:", p)
			}
		}
		if showSpinner {
			spin = newSpinner(fmt.Sprintf("checking %d repositories…", len(repos)))
		}
	} else if spin != nil {
		spin.setMsg(fmt.Sprintf("checking %d repositories…", len(repos)))
	}

	resultsCh := make(chan result, len(repos))
	var wg sync.WaitGroup

	for _, repo := range repos {
		wg.Add(1)
		go func(repo string) {
			defer wg.Done()
			checkRepo(repo, home, disableLock, lockStaleAfter, stashStaleAfter, worktree, staleWorktreeAfter, resultsCh)
		}(repo)
	}

	wg.Wait()
	close(resultsCh)

	if spin != nil {
		spin.stop()
	}

	var lines []string
	for r := range resultsCh {
		lines = append(lines, r.display+" is "+r.status)
	}

	if len(lines) == 0 {
		fmt.Println("All repos are up to date")
		return
	}
	for _, l := range lines {
		fmt.Println(l)
	}
}

func repoDisplay(path, home string) string {
	if path == home {
		return "~"
	}
	if rel, ok := strings.CutPrefix(path, home+"/"); ok {
		return "~/" + rel
	}
	return path
}

func parseExtraRoots(home string) ([]string, error) {
	val := os.Getenv("CHECK_GIT_REPOS")
	if val == "" {
		return nil, nil
	}
	var roots []string
	for _, p := range strings.Split(val, ":") {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		if strings.HasPrefix(p, "~/") {
			p = home + "/" + p[2:]
		} else if p == "~" {
			p = home
		}
		p = filepath.Clean(p)
		fi, err := os.Stat(p)
		if err != nil {
			return nil, fmt.Errorf("CHECK_GIT_REPOS: %s: %w", p, err)
		}
		if !fi.IsDir() {
			return nil, fmt.Errorf("CHECK_GIT_REPOS: %s: not a directory", p)
		}
		roots = append(roots, p)
	}
	return roots, nil
}

func loadIgnore(home string) []string {
	path := filepath.Join(home, ".config", "check-git-repos-source", "ignore.txt")
	f, err := os.Open(path)
	if err != nil {
		return nil
	}
	defer f.Close()

	var paths []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "~/") {
			line = home + "/" + line[2:]
		} else if line == "~" {
			line = home
		}
		paths = append(paths, filepath.Clean(line))
	}
	return paths
}

func gitArgs(repo string, disableLock bool, args ...string) []string {
	out := []string{"-C", repo}
	if disableLock {
		out = append(out, "--no-optional-locks")
	}
	return append(out, args...)
}

// findCheckpoints returns the display names of every repository that contains a
// CHECKPOINT.md, sorted. It is the whole of --checkpoint mode: no fetch, no
// status, no lock scan, so it finishes in about a second where a full scan
// takes minutes.
//
// It deliberately does NOT reuse the CHECKPOINT status produced by checkRepo.
// That status comes from 'git status --porcelain', which reports only untracked
// files and collapses an entirely-untracked directory into one '?? dir/' entry —
// so it misses a CHECKPOINT.md sitting inside a brand-new directory, and misses
// one that was committed by mistake. Looking at the filesystem finds both.
func findCheckpoints(repos []string, repoSet map[string]struct{}, home string) []string {
	var mu sync.Mutex
	var found []string
	var wg sync.WaitGroup

	for _, repo := range repos {
		wg.Add(1)
		go func(repo string) {
			defer wg.Done()
			if !hasCheckpointFile(repo, repoSet) {
				return
			}
			mu.Lock()
			found = append(found, repoDisplay(repo, home))
			mu.Unlock()
		}(repo)
	}
	wg.Wait()

	sort.Strings(found)
	return found
}

// hasCheckpointFile reports whether a CHECKPOINT.md exists anywhere in a
// repository's working tree.
//
// The whole tree is searched rather than just the root for two reasons. In a
// tracking repository — ~/admin and /opt/containers, which hold many small
// projects one per top-level directory — a project's CHECKPOINT.md belongs in
// that project's own directory rather than at the repo root, so a root-only test
// is not sufficient there. And a checkpoint written into a newly created
// subdirectory is invisible to 'git status --porcelain', which collapses an
// entirely-untracked directory into a single '?? dir/' entry.
func hasCheckpointFile(repo string, repoSet map[string]struct{}) bool {
	found := false
	filepath.WalkDir(repo, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
		if err != nil {
			return filepath.SkipDir
		}
		if d.IsDir() {
			if d.Name() == ".git" {
				return filepath.SkipDir
			}
			// A nested repository is scanned as its own entry, so a checkpoint
			// inside it is reported against that repo rather than this one.
			if path != repo {
				if _, nested := repoSet[path]; nested {
					return filepath.SkipDir
				}
			}
			return nil
		}
		if d.Name() == "CHECKPOINT.md" {
			found = true
			return filepath.SkipAll
		}
		return nil
	})
	return found
}

// isCheckpointEntry reports whether a '?? ' porcelain line refers to a
// CHECKPOINT.md file.
//
// CHECKPOINT.md is the crash-resumable work checkpoint written by AI agents
// working on this host. It is deliberately never committed and deliberately
// never added to .gitignore — being untracked is the whole point, because that
// is what makes a leftover one visible. Reporting it as UNTRACKED alongside
// genuinely forgotten files defeats that: every repo with an in-flight session
// looks like it has uncommitted work. It gets its own status instead, so the
// signal survives without masquerading as something else.
//
// Note that 'git status --porcelain' collapses an entirely-untracked directory
// into a single '?? dir/' entry, so a CHECKPOINT.md inside a brand-new
// directory is still reported as UNTRACKED. Detecting that would need
// --untracked-files=all, which is materially slower across every repo in $HOME.
func isCheckpointEntry(line string) bool {
	path := strings.TrimPrefix(line[2:], " ")
	// Git quotes paths containing special characters; CHECKPOINT.md never
	// needs quoting, so an opening quote is enough to rule the entry out.
	if strings.HasPrefix(path, `"`) {
		return false
	}
	return filepath.Base(path) == "CHECKPOINT.md"
}

func checkRepo(repo, home string, disableLock bool, lockStaleAfter, stashStaleAfter time.Duration, worktree bool, staleWorktreeAfter time.Duration, ch chan<- result) {
	display := repoDisplay(repo, home)

	// Scan for lock files BEFORE running any git command against this repo.
	// Every git invocation below can create *.lock files of its own, and
	// 'git fetch' additionally spawns a detached 'git maintenance run --auto'
	// that keeps creating them after fetch has returned. Checking first is what
	// keeps the tool from reporting its own locks back to the user as LOCKED.
	locked := hasLockFiles(repo, lockStaleAfter)

	if !disableLock {
		// maintenance.auto=false / gc.auto=0 stop 'git fetch' from spawning the
		// detached background maintenance process. This is a read-only status
		// scan over every repo in $HOME — it has no business kicking off repacks.
		exec.Command("git", "-C", repo, //nolint:errcheck
			"-c", "maintenance.auto=false",
			"-c", "gc.auto=0",
			"fetch", "--quiet").Run()
	}

	var statuses []string

	ahead := revCount(repo, disableLock, "@{u}..HEAD")
	if ahead >= 0 {
		behind := revCount(repo, disableLock, "HEAD..@{u}")
		if behind >= 0 {
			switch {
			case ahead > 0 && behind > 0:
				statuses = append(statuses, "AHEAD and BEHIND (diverged)")
			case ahead > 0:
				statuses = append(statuses, "AHEAD")
			case behind > 0:
				statuses = append(statuses, "BEHIND")
			}
		}
	}

	out, err := exec.Command("git", gitArgs(repo, disableLock, "status", "--porcelain")...).Output()
	if err == nil {
		var hasStaged, hasUnstaged, hasUntracked, hasCheckpoint bool
		for _, line := range strings.Split(string(out), "\n") {
			if len(line) < 2 {
				continue
			}
			x, y := line[0], line[1]
			if x != ' ' && x != '?' {
				hasStaged = true
			}
			if y != ' ' && y != '?' {
				hasUnstaged = true
			}
			if x == '?' && y == '?' {
				if isCheckpointEntry(line) {
					hasCheckpoint = true
				} else {
					hasUntracked = true
				}
			}
		}
		if hasStaged {
			statuses = append(statuses, "STAGED")
		}
		if hasUnstaged {
			statuses = append(statuses, "UNSTAGED")
		}
		if hasUntracked {
			statuses = append(statuses, "UNTRACKED")
		}
		if hasCheckpoint {
			statuses = append(statuses, "CHECKPOINT")
		}
	}

	if locked {
		statuses = append(statuses, "LOCKED")
	}

	// hasStale tracks whether STALE has already been appended, so a repo that
	// is flagged stale for both an old stash and an old worktree still reports
	// the word once rather than twice.
	hasStale := false
	addStale := func() {
		if !hasStale {
			statuses = append(statuses, "STALE")
			hasStale = true
		}
	}

	// STASH and STALE are mutually exclusive by design: a repo holding both a
	// fresh and an old stash reports STALE, because the old one is the actionable
	// finding and reporting both would bury it.
	if has, stale := stashState(repo, disableLock, stashStaleAfter); has {
		if stale {
			addStale()
		} else {
			statuses = append(statuses, "STASH")
		}
	}

	// WT and STALE are not mutually exclusive: an old worktree is still a
	// worktree, so both are reported together rather than STALE replacing WT.
	if worktree {
		if has, stale := worktreeState(repo, disableLock, staleWorktreeAfter); has {
			statuses = append(statuses, "WT")
			if stale {
				addStale()
			}
		}
	}

	if len(statuses) == 0 {
		return
	}
	ch <- result{display, strings.Join(statuses, ", ")}
}

// isStaleLock reports whether a *.lock file is old enough to be considered
// abandoned. A staleAfter of 0 disables the age test entirely.
func isStaleLock(d os.DirEntry, staleAfter time.Duration) bool {
	if staleAfter == 0 {
		return true
	}
	info, err := d.Info()
	if err != nil {
		// The file vanished between the walk and the stat, which means some
		// live git process just released it. Not stale.
		return false
	}
	return time.Since(info.ModTime()) >= staleAfter
}

func hasLockFiles(repo string, staleAfter time.Duration) bool {
	gitDir := filepath.Join(repo, ".git")
	found := false
	filepath.WalkDir(gitDir, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
		if err != nil || d.IsDir() || !strings.HasSuffix(path, ".lock") {
			return nil
		}
		if !isStaleLock(d, staleAfter) {
			return nil
		}
		found = true
		return filepath.SkipAll
	})
	return found
}

func removeStaleLocks(repos []string, home string, staleAfter time.Duration) []string {
	var removed []string
	for _, repo := range repos {
		gitDir := filepath.Join(repo, ".git")
		filepath.WalkDir(gitDir, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
			if err != nil || d.IsDir() || !strings.HasSuffix(path, ".lock") {
				return nil
			}
			// Never remove a lock a live git process may still be holding —
			// deleting it would corrupt the operation that owns it.
			if !isStaleLock(d, staleAfter) {
				return nil
			}
			if os.Remove(path) == nil {
				removed = append(removed, repoDisplay(path, home))
			}
			return nil
		})
	}
	return removed
}

func revCount(repo string, disableLock bool, refRange string) int {
	out, err := exec.Command("git", gitArgs(repo, disableLock, "rev-list", "--count", refRange)...).Output()
	if err != nil {
		return -1
	}
	n := 0
	_, err = fmt.Fscan(bytes.NewReader(out), &n)
	if err != nil {
		return -1
	}
	return n
}

// filterParentIgnored removes any repo that is gitignored by an enclosing repo.
// This handles nested clones (e.g. example repos cloned inside a parent repo that
// lists them in its .gitignore) without requiring manual ignore file entries.
func filterParentIgnored(repos []string, repoSet map[string]struct{}) []string {
	var out []string
	for _, repo := range repos {
		parent := closestAncestorRepo(repo, repoSet)
		if parent != "" && isGitIgnoredBy(parent, repo) {
			continue
		}
		out = append(out, repo)
	}
	return out
}

func closestAncestorRepo(repoPath string, repoSet map[string]struct{}) string {
	dir := filepath.Dir(repoPath)
	for {
		next := filepath.Dir(dir)
		if next == dir {
			return ""
		}
		if _, ok := repoSet[dir]; ok {
			return dir
		}
		dir = next
	}
}

func isGitIgnoredBy(parentRepo, childPath string) bool {
	rel, err := filepath.Rel(parentRepo, childPath)
	if err != nil {
		return false
	}
	return exec.Command("git", "-C", parentRepo, "check-ignore", "-q", rel).Run() == nil
}

package main

import (
	"bufio"
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

const version = "1.8.1"

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
	var disableLock bool
	var ignorePrefix bool
	var removeLocks bool
	for _, arg := range os.Args[1:] {
		switch arg {
		case "--version", "-v":
			fmt.Println("check-git-repos v" + version)
			os.Exit(0)
		case "--help", "-h":
			fmt.Print("Usage: check-git-repos [--version] [--help] [--batch-mode] [--disable-lock] [--ignore-prefix] [--remove-locks]\n\n" +
				"Scans all git repositories under $HOME (and any paths listed in\n" +
				"$CHECK_GIT_REPOS) and reports any that are ahead, behind, diverged\n" +
				"from their upstream, or have a dirty working tree.\n\n" +
				"Options:\n" +
				"  --version        Print version and exit\n" +
				"  --help           Print this help and exit\n" +
				"  --batch-mode     Suppress the progress spinner (for systemd/cron)\n" +
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
				"                   Prints each removed path. Only run this when no other\n" +
				"                   git processes are active — removing a live lock file\n" +
				"                   will corrupt the operation holding it.\n\n" +
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
				"  LOCKED           Stale *.lock files present under .git/\n\n" +
				"Ignore file: ~/.config/check-git-repos-source/ignore.txt\n" +
				"  One path per line (~ expanded). Repos under those paths are skipped.\n" +
				"  Lines beginning with # are treated as comments.\n")
			os.Exit(0)
		case "--batch-mode":
			batchMode = true
		case "--disable-lock":
			disableLock = true
		case "--ignore-prefix":
			ignorePrefix = true
		case "--remove-locks":
			removeLocks = true
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

	if removeLocks {
		if spin != nil {
			spin.stop()
			spin = nil
		}
		removed := removeStaleLocks(repos, home)
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
			checkRepo(repo, home, disableLock, resultsCh)
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

func checkRepo(repo, home string, disableLock bool, ch chan<- result) {
	display := repoDisplay(repo, home)

	if !disableLock {
		exec.Command("git", "-C", repo, "fetch", "--quiet").Run() //nolint:errcheck
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
		var hasStaged, hasUnstaged, hasUntracked bool
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
				hasUntracked = true
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
	}

	if hasLockFiles(repo) {
		statuses = append(statuses, "LOCKED")
	}

	if len(statuses) == 0 {
		return
	}
	ch <- result{display, strings.Join(statuses, ", ")}
}

func hasLockFiles(repo string) bool {
	gitDir := filepath.Join(repo, ".git")
	found := false
	filepath.WalkDir(gitDir, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
		if err != nil || d.IsDir() || !strings.HasSuffix(path, ".lock") {
			return nil
		}
		found = true
		return filepath.SkipAll
	})
	return found
}

func removeStaleLocks(repos []string, home string) []string {
	var removed []string
	for _, repo := range repos {
		gitDir := filepath.Join(repo, ".git")
		filepath.WalkDir(gitDir, func(path string, d os.DirEntry, err error) error { //nolint:errcheck
			if err != nil || d.IsDir() || !strings.HasSuffix(path, ".lock") {
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

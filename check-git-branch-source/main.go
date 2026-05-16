package main

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
	"strings"
	"sync"
	"time"
)

const version = "1.0.0"

type result struct {
	line string
}

type spinner struct {
	mu   sync.Mutex
	msg  string
	done chan struct{}
	wg   sync.WaitGroup
}

func newSpinner(msg string) *spinner {
	s := &spinner{msg: msg, done: make(chan struct{})}
	s.wg.Go(func() {
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
	})
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

func repoDisplay(path, home string) string {
	if path == home {
		return "~"
	}
	if rel, ok := strings.CutPrefix(path, home+"/"); ok {
		return "~/" + rel
	}
	return path
}

func parseRoots(home string) ([]string, error) {
	val := os.Getenv("CHECK_GIT_BRANCH")
	if val == "" {
		return []string{home}, nil
	}
	var roots []string
	seen := make(map[string]struct{})
	for p := range strings.SplitSeq(val, ":") {
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
		if _, already := seen[p]; already {
			continue
		}
		fi, err := os.Stat(p)
		if err != nil {
			return nil, fmt.Errorf("CHECK_GIT_BRANCH: %s: %w", p, err)
		}
		if !fi.IsDir() {
			return nil, fmt.Errorf("CHECK_GIT_BRANCH: %s: not a directory", p)
		}
		seen[p] = struct{}{}
		roots = append(roots, p)
	}
	if len(roots) == 0 {
		return nil, fmt.Errorf("CHECK_GIT_BRANCH is set but contains no valid paths")
	}
	return roots, nil
}

func loadIgnore(home string) []string {
	path := filepath.Join(home, ".config", "check-git-branch", "ignore.txt")
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

// getDefaultBranch returns the default branch name for the repo's origin remote,
// or an empty string plus an error status string describing why it can't be determined.
func getDefaultBranch(repo string) (branch string, errStatus string) {
	out, err := exec.Command("git", "-C", repo, "remote").Output()
	if err != nil {
		return "", "REMOTE CANNOT BE DETERMINED"
	}
	if !slices.Contains(strings.Fields(string(out)), "origin") {
		return "", "LOCAL ONLY"
	}

	out, err = exec.Command("git", "-C", repo, "symbolic-ref", "refs/remotes/origin/HEAD").Output()
	if err != nil {
		return "", "ORIGIN/HEAD ISN'T SET"
	}
	ref := strings.TrimSpace(string(out))
	const prefix = "refs/remotes/origin/"
	if !strings.HasPrefix(ref, prefix) {
		return "", "REMOTE CANNOT BE DETERMINED"
	}
	return ref[len(prefix):], ""
}

func getCurrentBranch(repo string) (string, error) {
	out, err := exec.Command("git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD").Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

func getLocalBranches(repo string) ([]string, error) {
	out, err := exec.Command("git", "-C", repo, "branch", "--format=%(refname:short)").Output()
	if err != nil {
		return nil, err
	}
	var branches []string
	for b := range strings.SplitSeq(string(out), "\n") {
		b = strings.TrimSpace(b)
		if b != "" {
			branches = append(branches, b)
		}
	}
	return branches, nil
}

func checkRepo(repo, home string, ch chan<- result) {
	display := repoDisplay(repo, home)

	// Skip repos with no commits — branch state is meaningless there.
	if err := exec.Command("git", "-C", repo, "rev-parse", "HEAD").Run(); err != nil {
		return
	}

	defaultBranch, errStatus := getDefaultBranch(repo)
	if errStatus != "" {
		ch <- result{display + " - " + errStatus}
		return
	}

	currentBranch, err := getCurrentBranch(repo)
	if err != nil {
		ch <- result{display + " - REMOTE CANNOT BE DETERMINED"}
		return
	}

	localBranches, err := getLocalBranches(repo)
	if err != nil {
		ch <- result{display + " - REMOTE CANNOT BE DETERMINED"}
		return
	}

	var parts []string

	// Job 1: report if not on the default branch.
	if currentBranch != defaultBranch {
		parts = append(parts, "NOT AT DEFAULT BRANCH ("+currentBranch+")")
	}

	// Job 2: list all non-default local branches except the current one
	// (the current is already named in job 1 when it is non-default).
	var otherBranches []string
	for _, b := range localBranches {
		if b == defaultBranch || b == currentBranch {
			continue
		}
		otherBranches = append(otherBranches, b)
	}
	if len(otherBranches) > 0 {
		parts = append(parts, "non-current local branches: "+strings.Join(otherBranches, ", "))
	}

	if len(parts) == 0 {
		return
	}
	ch <- result{display + " - " + strings.Join(parts, " | ")}
}

func main() {
	var batchMode bool
	var ignorePrefix bool
	for _, arg := range os.Args[1:] {
		switch arg {
		case "--version", "-v":
			fmt.Println("check-git-branch v" + version)
			os.Exit(0)
		case "--help", "-h":
			fmt.Print("Usage: check-git-branch [--version] [--help] [--batch-mode] [--ignore-prefix]\n\n" +
				"Scans all git repositories under $HOME (or paths listed in $CHECK_GIT_BRANCH)\n" +
				"and reports any that are not on their default branch or that have non-default\n" +
				"local branches lingering from previous work.\n\n" +
				"Options:\n" +
				"  --version        Print version and exit\n" +
				"  --help           Print this help and exit\n" +
				"  --batch-mode     Suppress the progress spinner (for systemd/cron)\n" +
				"  --ignore-prefix  Treat each entry in the ignore file as a plain text\n" +
				"                   path-prefix instead of an exact path or path-component\n" +
				"                   prefix. With this flag an ignore entry of\n" +
				"                   ~/Projects/workspaces/DOSD also skips repos under\n" +
				"                   ~/Projects/workspaces/DOSD-5844, DOSD-5904, etc.\n\n" +
				"Environment:\n" +
				"  CHECK_GIT_BRANCH  Colon-separated list of directory paths to scan for\n" +
				"                    git repositories, e.g.:\n" +
				"                      export CHECK_GIT_BRANCH=~/Projects:~/work\n" +
				"                    ~ is expanded. Every listed path must exist and be a\n" +
				"                    directory — the program exits with an error otherwise.\n" +
				"                    When this variable is not set, $HOME is scanned.\n\n" +
				"Output (one line per repo, silent if everything is clean):\n" +
				"  NOT AT DEFAULT BRANCH (name)   Current branch differs from the remote default\n" +
				"  non-current local branches: …  Non-default local branches exist (stale work)\n" +
				"  LOCAL ONLY                     No remote configured\n" +
				"  ORIGIN/HEAD ISN'T SET          origin remote exists but HEAD ref is unset\n" +
				"  REMOTE CANNOT BE DETERMINED    git remote query failed\n\n" +
				"Both conditions appear on the same line separated by \" | \" when both fire.\n\n" +
				"Ignore file: ~/.config/check-git-branch/ignore.txt\n" +
				"  One path per line (~ expanded). Repos under those paths are skipped.\n" +
				"  Lines beginning with # are treated as comments.\n")
			os.Exit(0)
		case "--batch-mode":
			batchMode = true
		case "--ignore-prefix":
			ignorePrefix = true
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

	roots, err := parseRoots(home)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}

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

	if spin != nil {
		spin.setMsg(fmt.Sprintf("checking %d repositories…", len(repos)))
	}

	resultsCh := make(chan result, len(repos))
	var wg sync.WaitGroup

	for _, repo := range repos {
		wg.Go(func() {
			checkRepo(repo, home, resultsCh)
		})
	}

	wg.Wait()
	close(resultsCh)

	if spin != nil {
		spin.stop()
	}

	for r := range resultsCh {
		fmt.Println(r.line)
	}
}

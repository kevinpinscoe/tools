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

const version = "1.4.0"

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
	for _, arg := range os.Args[1:] {
		switch arg {
		case "--version", "-v":
			fmt.Println("check-git-repos v" + version)
			os.Exit(0)
		case "--help", "-h":
			fmt.Print("Usage: check-git-repos [--version] [--help] [--batch-mode] [--disable-lock]\n\n" +
				"Scans all git repositories under $HOME and reports any that are\n" +
				"ahead, behind, diverged from their upstream, or have a dirty\n" +
				"working tree (staged, unstaged, or untracked changes).\n\n" +
				"Options:\n" +
				"  --version       Print version and exit\n" +
				"  --help          Print this help and exit\n" +
				"  --batch-mode    Suppress the progress spinner (for systemd/cron)\n" +
				"  --disable-lock  Avoid acquiring git lock files. Skips 'git fetch'\n" +
				"                  entirely and passes --no-optional-locks to all git\n" +
				"                  invocations. Use this when another git process (an\n" +
				"                  IDE, another scan) may be running concurrently.\n" +
				"                  WARNING: AHEAD/BEHIND results reflect whatever the\n" +
				"                  last fetch saw — they will be stale relative to the\n" +
				"                  remote. Dirty-tree detection is unaffected.\n\n" +
				"Ignore file: ~/.config/check-git-repos-source/ignore.txt\n" +
				"  One path per line (~ expanded). Repos under those paths are skipped.\n" +
				"  Lines beginning with # are treated as comments.\n")
			os.Exit(0)
		case "--batch-mode":
			batchMode = true
		case "--disable-lock":
			disableLock = true
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

	var spin *spinner
	if showSpinner {
		spin = newSpinner("scanning for repositories…")
	}

	var repos []string
	err = filepath.WalkDir(home, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return filepath.SkipDir
		}
		if d.IsDir() {
			for _, ig := range ignorePaths {
				if path == ig || strings.HasPrefix(path, ig+string(filepath.Separator)) {
					return filepath.SkipDir
				}
			}
			if d.Name() == ".git" {
				repos = append(repos, filepath.Dir(path))
				return filepath.SkipDir
			}
		}
		return nil
	})
	if err != nil {
		if spin != nil {
			spin.stop()
		}
		fmt.Fprintln(os.Stderr, "error walking home directory:", err)
		os.Exit(1)
	}

	if spin != nil {
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
	display := "~/" + strings.TrimPrefix(repo, home+"/")
	if repo == home {
		display = "~"
	}

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

	if len(statuses) == 0 {
		return
	}
	ch <- result{display, strings.Join(statuses, ", ")}
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

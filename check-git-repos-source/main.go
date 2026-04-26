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
)

const version = "1.1.0"

type result struct {
	display string
	status  string
}

func main() {
	for _, arg := range os.Args[1:] {
		switch arg {
		case "--version", "-v":
			fmt.Println("check-git-repos v" + version)
			os.Exit(0)
		case "--help", "-h":
			fmt.Print("Usage: check-git-repos [--version] [--help]\n\n" +
				"Scans all git repositories under $HOME and reports any that are\n" +
				"ahead, behind, or diverged from their upstream branch.\n\n" +
				"Options:\n" +
				"  --version   Print version and exit\n" +
				"  --help      Print this help and exit\n\n" +
				"Ignore file: ~/.config/check-git-repos-source/ignore.txt\n" +
				"  One path per line (~ expanded). Repos under those paths are skipped.\n" +
				"  Lines beginning with # are treated as comments.\n")
			os.Exit(0)
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

	ignorePaths := loadIgnore(home)

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
		fmt.Fprintln(os.Stderr, "error walking home directory:", err)
		os.Exit(1)
	}

	resultsCh := make(chan result, len(repos))
	var wg sync.WaitGroup

	for _, repo := range repos {
		wg.Add(1)
		go func(repo string) {
			defer wg.Done()
			checkRepo(repo, home, resultsCh)
		}(repo)
	}

	wg.Wait()
	close(resultsCh)

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

func checkRepo(repo, home string, ch chan<- result) {
	display := "~/" + strings.TrimPrefix(repo, home+"/")
	if repo == home {
		display = "~"
	}

	exec.Command("git", "-C", repo, "fetch", "--quiet").Run() //nolint:errcheck

	ahead := revCount(repo, "@{u}..HEAD")
	if ahead < 0 {
		return // no upstream
	}
	behind := revCount(repo, "HEAD..@{u}")
	if behind < 0 {
		return
	}

	switch {
	case ahead > 0 && behind > 0:
		ch <- result{display, "AHEAD and BEHIND (diverged)"}
	case ahead > 0:
		ch <- result{display, "AHEAD"}
	case behind > 0:
		ch <- result{display, "BEHIND"}
	}
}

func revCount(repo, refRange string) int {
	out, err := exec.Command("git", "-C", repo, "rev-list", "--count", refRange).Output()
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

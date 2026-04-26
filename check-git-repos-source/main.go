package main

import (
	"bytes"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
)

type result struct {
	display string
	status  string
}

func main() {
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Fprintln(os.Stderr, "error: cannot determine home directory:", err)
		os.Exit(1)
	}

	var repos []string
	err = filepath.WalkDir(home, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return filepath.SkipDir
		}
		if d.IsDir() && d.Name() == ".git" {
			repos = append(repos, filepath.Dir(path))
			return filepath.SkipDir
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

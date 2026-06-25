// menu-app presents the scripts listed in a repository's .menu-app.yaml file
// as a simple terminal menu. Selecting an entry runs its script (relative to
// the git root) and then returns to the menu.
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"gopkg.in/yaml.v3"
)

// version is overridden at build time via -ldflags "-X main.version=...".
var version = "dev"

// configName is the menu definition file menu-app looks for at the git root.
const configName = ".menu-app.yaml"

// templateYAML is written to the git root when the user accepts the offer to
// create a starter config. It mirrors ~/tools/menu-app-template.yaml.
const templateYAML = `# .menu-app.yaml
#
# menu-app reads this file from the root of your git repository and shows each
# entry below as a selectable menu item. Selecting an item runs its script and
# then returns you to the menu.
#
# Rules:
#   - "script" is a path RELATIVE TO THE GIT ROOT.
#   - Each script must be executable (chmod +x path/to/script).
#   - Scripts run with the git root as their working directory.
#
# Keep this file at the top level of your repository, named ".menu-app.yaml".

items:
  - name: Run tests
    script: scripts/test.sh

  - name: Build project
    script: scripts/build.sh

  - name: Deploy
    script: scripts/deploy.sh
`

var (
	docStyle = lipgloss.NewStyle().Margin(1, 2)
	okStyle  = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("42"))
	errStyle = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("196"))
)

// config is the parsed .menu-app.yaml file.
type config struct {
	Items []menuItem `yaml:"items"`
}

type menuItem struct {
	Name   string `yaml:"name"`
	Script string `yaml:"script"`
}

// listItem adapts a menuItem to the bubbles list.Item interface.
type listItem struct {
	name   string
	script string
}

func (i listItem) Title() string       { return i.name }
func (i listItem) Description() string { return i.script }
func (i listItem) FilterValue() string { return i.name }

type uiState int

const (
	stateMenu uiState = iota
	stateResult
)

// scriptDone is delivered after a selected script finishes running.
type scriptDone struct {
	name string
	err  error
}

type model struct {
	list     list.Model
	gitRoot  string
	state    uiState
	result   string
	quitting bool
}

func (m model) Init() tea.Cmd { return nil }

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		h, v := docStyle.GetFrameSize()
		m.list.SetSize(msg.Width-h, msg.Height-v)
		return m, nil

	case scriptDone:
		m.state = stateResult
		m.result = resultText(msg)
		return m, nil

	case tea.KeyMsg:
		// On the result screen any key returns to the menu.
		if m.state == stateResult {
			m.state = stateMenu
			return m, nil
		}
		// While the list filter is active, let the list consume keys.
		if m.list.FilterState() != list.Filtering {
			switch msg.String() {
			case "ctrl+c", "q":
				m.quitting = true
				return m, tea.Quit
			case "enter":
				return m.runSelected()
			}
		}
	}

	var cmd tea.Cmd
	m.list, cmd = m.list.Update(msg)
	return m, cmd
}

// runSelected runs the script for the highlighted menu item. The TUI is
// suspended while the script runs and resumed when it exits.
func (m model) runSelected() (tea.Model, tea.Cmd) {
	it, ok := m.list.SelectedItem().(listItem)
	if !ok {
		return m, nil
	}

	abs := filepath.Join(m.gitRoot, it.script)
	info, err := os.Stat(abs)
	if err != nil {
		m.state = stateResult
		m.result = errStyle.Render(fmt.Sprintf("✗ Cannot run %q:\n  %v", it.name, err)) +
			"\n\nPress any key to return to the menu."
		return m, nil
	}
	if info.IsDir() {
		m.state = stateResult
		m.result = errStyle.Render(fmt.Sprintf("✗ Cannot run %q:\n  %s is a directory, not a script", it.name, it.script)) +
			"\n\nPress any key to return to the menu."
		return m, nil
	}

	cmd := exec.Command(abs)
	cmd.Dir = m.gitRoot
	return m, tea.ExecProcess(cmd, func(err error) tea.Msg {
		return scriptDone{name: it.name, err: err}
	})
}

func (m model) View() string {
	if m.quitting {
		return ""
	}
	if m.state == stateResult {
		return docStyle.Render(m.result)
	}
	return docStyle.Render(m.list.View())
}

// resultText builds the message shown after a script finishes.
func resultText(d scriptDone) string {
	suffix := "\n\nPress any key to return to the menu."
	if d.err == nil {
		return okStyle.Render(fmt.Sprintf("✓ %q finished successfully.", d.name)) + suffix
	}
	var exitErr *exec.ExitError
	if errors.As(d.err, &exitErr) {
		return errStyle.Render(fmt.Sprintf("✗ %q exited with code %d.", d.name, exitErr.ExitCode())) + suffix
	}
	return errStyle.Render(fmt.Sprintf("✗ %q failed to run:\n  %v", d.name, d.err)) + suffix
}

func main() {
	versionFlag := flag.Bool("version", false, "Print version and exit.")
	flag.Usage = usage
	flag.Parse()

	if *versionFlag {
		fmt.Printf("menu-app %s\n", version)
		return
	}

	if _, err := exec.LookPath("git"); err != nil {
		fatal("git is not installed or not found in PATH")
	}

	root, err := findGitRoot()
	if err != nil {
		fatal("not a git initialized directory")
	}

	cfgPath := filepath.Join(root, configName)
	data, err := os.ReadFile(cfgPath)
	if errors.Is(err, os.ErrNotExist) {
		if err := offerCreate(cfgPath); err != nil {
			fatal(err.Error())
		}
		return
	} else if err != nil {
		fatal(fmt.Sprintf("reading %s: %v", cfgPath, err))
	}

	var cfg config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		fatal(fmt.Sprintf("parsing %s:\n  %v", cfgPath, err))
	}
	if len(cfg.Items) == 0 {
		fatal(fmt.Sprintf("%s defines no menu items (expected a top-level 'items:' list)", cfgPath))
	}

	items := make([]list.Item, 0, len(cfg.Items))
	for _, mi := range cfg.Items {
		if strings.TrimSpace(mi.Name) == "" || strings.TrimSpace(mi.Script) == "" {
			fatal(fmt.Sprintf("%s: every item needs both a 'name' and a 'script'", cfgPath))
		}
		items = append(items, listItem{name: mi.Name, script: mi.Script})
	}

	l := list.New(items, list.NewDefaultDelegate(), 0, 0)
	l.Title = "menu-app — " + filepath.Base(root)
	m := model{list: l, gitRoot: root, state: stateMenu}

	if _, err := tea.NewProgram(m, tea.WithAltScreen()).Run(); err != nil {
		fatal(err.Error())
	}
}

// findGitRoot returns the top level of the git repository containing the
// current directory, or an error if the current directory is not in one.
func findGitRoot() (string, error) {
	out, err := exec.Command("git", "rev-parse", "--show-toplevel").Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// offerCreate prompts the user to create a starter .menu-app.yaml from the
// built-in template.
func offerCreate(path string) error {
	fmt.Printf("No %s found at the git root:\n  %s\n\nCreate one from the template? [y/N] ", configName, path)

	var resp string
	fmt.Scanln(&resp) // empty input leaves resp == "" (a "no")
	switch strings.ToLower(strings.TrimSpace(resp)) {
	case "y", "yes":
		if err := os.WriteFile(path, []byte(templateYAML), 0o644); err != nil {
			return fmt.Errorf("creating %s: %w", path, err)
		}
		fmt.Printf("\nCreated %s\nEdit it to define your menu items, then run menu-app again.\n", path)
	default:
		fmt.Println("\nAborted. No file created.")
	}
	return nil
}

func usage() {
	fmt.Fprintf(os.Stderr, `menu-app — run repository scripts from a simple TUI menu.

Usage:
  menu-app [flags]

menu-app looks for a file named %s at the root of the current git
repository. Each entry in that file becomes a menu item; selecting an item
runs its script (relative to the git root) and then returns you to the menu.

Flags:
  -version    Print version and exit.
  -h, -help   Show this help.

Behavior:
  * Not inside a git repository       -> prints an error and exits.
  * Inside a repo but no %s  -> offers to create one from a template.

Keys (in the menu):
  enter   run the highlighted script
  /       filter the list
  q       quit
`, configName, configName)
}

func fatal(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}

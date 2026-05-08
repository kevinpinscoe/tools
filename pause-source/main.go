package main

import (
	"fmt"
	"os"
	"strconv"
	"sync"
	"time"
)

const version = "1.0.0"

func formatDuration(secs int) string {
	if secs > 60 {
		return fmt.Sprintf("%dm %ds", secs/60, secs%60)
	}
	return fmt.Sprintf("%d seconds", secs)
}

func formatRemaining(secs int) string {
	if secs > 60 {
		return fmt.Sprintf("%dm %ds", secs/60, secs%60)
	}
	return fmt.Sprintf("%ds", secs)
}

func isTerminal(f *os.File) bool {
	fi, err := f.Stat()
	if err != nil {
		return false
	}
	return fi.Mode()&os.ModeCharDevice != 0
}

type display struct {
	done  chan struct{}
	wg    sync.WaitGroup
	total int
	start time.Time
	label string
}

func newDisplay(total int) *display {
	return &display{
		done:  make(chan struct{}),
		total: total,
		start: time.Now(),
		label: "Pausing for " + formatDuration(total),
	}
}

func (d *display) run() {
	d.wg.Add(1)
	go func() {
		defer d.wg.Done()
		frames := []string{"⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"}
		i := 0
		for {
			select {
			case <-d.done:
				fmt.Fprint(os.Stderr, "\r\033[K")
				return
			default:
				remaining := max(0, d.total-int(time.Since(d.start).Seconds()))
				fmt.Fprintf(os.Stderr, "\r%s   %s   %s remaining",
					d.label, frames[i%len(frames)], formatRemaining(remaining))
				i++
				time.Sleep(100 * time.Millisecond)
			}
		}
	}()
}

func (d *display) stop() {
	close(d.done)
	d.wg.Wait()
}

func main() {
	for _, arg := range os.Args[1:] {
		switch arg {
		case "--version", "-v":
			fmt.Println("pause v" + version)
			os.Exit(0)
		case "--help", "-h":
			fmt.Print("Usage: pause <seconds>\n\n" +
				"Sleeps for the specified number of seconds. In a terminal, displays\n" +
				"a live countdown status line on stderr. Outside a terminal, prints\n" +
				"a single status message and sleeps silently.\n\n" +
				"Options:\n" +
				"  --version    Print version and exit\n" +
				"  --help       Print this help and exit\n\n" +
				"Examples:\n" +
				"  pause 30     # pause for 30 seconds\n" +
				"  pause 90     # pause for 1m 30s with live countdown\n")
			os.Exit(0)
		}
	}

	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "error: seconds argument is required")
		fmt.Fprintln(os.Stderr, "Usage: pause <seconds>")
		os.Exit(1)
	}

	secs, err := strconv.Atoi(os.Args[1])
	if err != nil || secs < 0 {
		fmt.Fprintf(os.Stderr, "error: invalid seconds value: %q\n", os.Args[1])
		os.Exit(1)
	}

	if isTerminal(os.Stderr) {
		d := newDisplay(secs)
		d.run()
		time.Sleep(time.Duration(secs) * time.Second)
		d.stop()
	} else {
		fmt.Fprintln(os.Stderr, "Waiting for "+formatDuration(secs))
		time.Sleep(time.Duration(secs) * time.Second)
	}
}

package output

import (
	"fmt"
	"os"
	"strings"

	"golang.org/x/term"
)

// Mode represents the output format.
type Mode string

const (
	ModeHuman Mode = "human"
	ModePlain Mode = "plain"
)

// Global output mode for the current session.
var CurrentMode Mode = ModeHuman

// Resolve determines output mode from explicit flag or TTY auto-detection.
func Resolve(explicit string) Mode {
	if explicit != "" {
		return Mode(explicit)
	}
	if term.IsTerminal(int(os.Stdout.Fd())) {
		return ModeHuman
	}
	return ModePlain
}

// IsPlain returns true if in plain output mode.
func IsPlain() bool {
	return CurrentMode == ModePlain
}

// PrintTablePlain prints a pipe-delimited table to stdout.
func PrintTablePlain(headers []string, rows [][]string) {
	fmt.Println(strings.Join(headers, "|"))
	for _, row := range rows {
		fmt.Println(strings.Join(row, "|"))
	}
}

// PrintTable prints a formatted table (plain or basic ASCII).
func PrintTable(headers []string, rows [][]string) {
	if IsPlain() {
		PrintTablePlain(headers, rows)
		return
	}

	// Calculate column widths
	widths := make([]int, len(headers))
	for i, h := range headers {
		widths[i] = len(h)
	}
	for _, row := range rows {
		for i, cell := range row {
			if i < len(widths) && len(cell) > widths[i] {
				widths[i] = len(cell)
			}
		}
	}

	// Print header
	var headerLine, sepLine strings.Builder
	for i, h := range headers {
		if i > 0 {
			headerLine.WriteString(" | ")
			sepLine.WriteString("-+-")
		}
		headerLine.WriteString(fmt.Sprintf("%-*s", widths[i], h))
		sepLine.WriteString(strings.Repeat("-", widths[i]))
	}
	fmt.Println(headerLine.String())
	fmt.Println(sepLine.String())

	// Print rows
	for _, row := range rows {
		var line strings.Builder
		for i, cell := range row {
			if i > 0 {
				line.WriteString(" | ")
			}
			if i < len(widths) {
				line.WriteString(fmt.Sprintf("%-*s", widths[i], cell))
			} else {
				line.WriteString(cell)
			}
		}
		fmt.Println(line.String())
	}
}

// StatusPrint prints a message only in human mode.
func StatusPrint(message string) {
	if !IsPlain() {
		fmt.Println(message)
	}
}

package output

import (
	"fmt"
	"os"
	"strings"

	"github.com/charmbracelet/lipgloss"
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

	// Calculate column widths using visible width (ANSI-aware).
	widths := make([]int, len(headers))
	for i, h := range headers {
		widths[i] = lipgloss.Width(h)
	}
	for _, row := range rows {
		for i, cell := range row {
			if i < len(widths) {
				if w := lipgloss.Width(cell); w > widths[i] {
					widths[i] = w
				}
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
		headerLine.WriteString(padVisible(h, widths[i]))
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
				line.WriteString(padVisible(cell, widths[i]))
			} else {
				line.WriteString(cell)
			}
		}
		fmt.Println(line.String())
	}
}

// padVisible left-justifies s to width w counting visible width (ignoring ANSI).
func padVisible(s string, w int) string {
	vw := lipgloss.Width(s)
	if vw >= w {
		return s
	}
	return s + strings.Repeat(" ", w-vw)
}

// StatusPrint prints a message only in human mode.
func StatusPrint(message string) {
	if !IsPlain() {
		fmt.Println(message)
	}
}

package debug

import (
	"encoding/json"
	"fmt"
	"os"
)

var enabled bool

// Enable turns on debug logging.
func Enable() {
	enabled = true
}

// IsEnabled returns whether debug mode is active.
func IsEnabled() bool {
	return enabled || os.Getenv("DEBUG") == "true" || os.Getenv("DEBUG") == "1"
}

// Log prints debug information to stderr.
func Log(label string, data any) {
	if !IsEnabled() {
		return
	}
	fmt.Fprintf(os.Stderr, "\n[DEBUG] %s:\n", label)
	switch v := data.(type) {
	case string:
		fmt.Fprintf(os.Stderr, "%s\n", v)
	default:
		b, err := json.MarshalIndent(v, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "%v\n", v)
		} else {
			fmt.Fprintf(os.Stderr, "%s\n", string(b))
		}
	}
}

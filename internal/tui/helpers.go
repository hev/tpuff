package tui

import (
	"encoding/json"
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

var vectorTypeRe = regexp.MustCompile(`^\[\d+\]f(?:16|32)$`)

// isVectorField detects if a value is a vector (array of numbers).
func isVectorField(val any) bool {
	switch v := val.(type) {
	case []any:
		if len(v) == 0 {
			return false
		}
		_, ok := v[0].(float64)
		return ok && len(v) > 8
	case []float64, []float32:
		return true
	}
	return false
}

// isVectorSchemaType checks if a schema type string matches vector pattern.
func isVectorSchemaType(typeStr string) bool {
	return vectorTypeRe.MatchString(typeStr)
}

// filterVectors removes vector fields from a document map.
func filterVectors(doc map[string]any, schemaDict map[string]any) map[string]any {
	result := make(map[string]any)
	for k, v := range doc {
		if k == "$dist" || k == "dist" {
			continue
		}
		// Check schema first
		if schemaDict != nil {
			if typeInfo, ok := schemaDict[k]; ok {
				var typeStr string
				switch t := typeInfo.(type) {
				case string:
					typeStr = t
				case map[string]any:
					if s, ok := t["type"].(string); ok {
						typeStr = s
					}
				}
				if isVectorSchemaType(typeStr) {
					continue
				}
			}
		}
		// Fallback: check value
		if isVectorField(v) {
			continue
		}
		result[k] = v
	}
	return result
}

// formatDocJSON formats a document as pretty-printed JSON, excluding vectors.
func formatDocJSON(doc map[string]any, schemaDict map[string]any) string {
	filtered := filterVectors(doc, schemaDict)
	b, err := json.MarshalIndent(filtered, "", "  ")
	if err != nil {
		return fmt.Sprintf("%v", doc)
	}
	return string(b)
}

// truncate truncates a string to maxLen with ellipsis.
func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	if maxLen <= 3 {
		return s[:maxLen]
	}
	return s[:maxLen-3] + "..."
}

// docPreviewLine creates a short one-line preview of a document.
func docPreviewLine(doc map[string]any, schemaDict map[string]any, maxLen int) string {
	filtered := filterVectors(doc, schemaDict)
	delete(filtered, "id")

	// Sort keys for consistency
	ks := make([]string, 0, len(filtered))
	for k := range filtered {
		ks = append(ks, k)
	}
	sort.Strings(ks)

	parts := make([]string, 0, len(ks))
	for _, k := range ks {
		v := filtered[k]
		var vs string
		switch val := v.(type) {
		case string:
			vs = val
		default:
			b, _ := json.Marshal(val)
			vs = string(b)
		}
		parts = append(parts, fmt.Sprintf("%s=%s", k, vs))
	}
	line := strings.Join(parts, " ")
	return truncate(line, maxLen)
}

// formatBytes formats byte count to human-readable string.
func formatBytes(b int64) string {
	if b == 0 {
		return "0 B"
	}
	const k = 1024
	sizes := []string{"B", "KB", "MB", "GB", "TB"}
	i := 0
	fb := float64(b)
	for fb >= float64(k) && i < len(sizes)-1 {
		fb /= float64(k)
		i++
	}
	return fmt.Sprintf("%.1f %s", fb, sizes[i])
}

// formatNumber formats an integer with commas.
func formatNumber(n int64) string {
	s := strconv.FormatInt(n, 10)
	if len(s) <= 3 {
		return s
	}
	var result []byte
	for i, c := range s {
		if i > 0 && (len(s)-i)%3 == 0 {
			result = append(result, ',')
		}
		result = append(result, byte(c))
	}
	return string(result)
}

// formatUpdatedAt formats a time to a short relative string.
func formatUpdatedAt(t time.Time) string {
	if t.IsZero() {
		return "N/A"
	}
	now := time.Now()
	if t.Year() == now.Year() && t.Month() == now.Month() && t.Day() == now.Day() {
		return t.Format("3:04 pm")
	}
	return t.Format("Jan 2, 2006")
}

// extractVectorInfo extracts vector attribute name and dimensions from schema.
func extractVectorInfo(schemaData map[string]any) (string, int) {
	re := regexp.MustCompile(`^\[(\d+)\]f(?:16|32)$`)
	for attrName, attrConfig := range schemaData {
		var typeStr string
		switch v := attrConfig.(type) {
		case string:
			typeStr = v
		case map[string]any:
			if t, ok := v["type"].(string); ok {
				typeStr = t
			}
		default:
			if b, err := json.Marshal(v); err == nil {
				var obj struct {
					Type string `json:"type"`
				}
				if json.Unmarshal(b, &obj) == nil {
					typeStr = obj.Type
				}
			}
		}
		if typeStr != "" {
			if m := re.FindStringSubmatch(typeStr); m != nil {
				dims, _ := strconv.Atoi(m[1])
				return attrName, dims
			}
		}
	}
	return "", 0
}

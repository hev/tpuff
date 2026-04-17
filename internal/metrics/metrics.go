package metrics

import (
	"fmt"
	"strings"
	"time"
)

// MetricValue is a single metric value with optional labels.
type MetricValue struct {
	Labels map[string]string
	Value  float64
}

// PrometheusMetric is a Prometheus metric with type, help text, and values.
type PrometheusMetric struct {
	Name   string
	Type   string // gauge, counter, histogram, summary
	Help   string
	Values []MetricValue
}

// EscapeLabel escapes special characters in Prometheus label values.
func EscapeLabel(value string) string {
	s := strings.ReplaceAll(value, `\`, `\\`)
	s = strings.ReplaceAll(s, `"`, `\"`)
	s = strings.ReplaceAll(s, "\n", `\n`)
	return s
}

// FormatMetric formats a single Prometheus metric in text exposition format.
func FormatMetric(m PrometheusMetric) string {
	var lines []string
	lines = append(lines, fmt.Sprintf("# HELP %s %s", m.Name, m.Help))
	lines = append(lines, fmt.Sprintf("# TYPE %s %s", m.Name, m.Type))

	for _, mv := range m.Values {
		var pairs []string
		for k, v := range mv.Labels {
			pairs = append(pairs, fmt.Sprintf(`%s="%s"`, k, EscapeLabel(v)))
		}
		labelStr := strings.Join(pairs, ",")

		if labelStr != "" {
			lines = append(lines, fmt.Sprintf("%s{%s} %v", m.Name, labelStr, mv.Value))
		} else {
			lines = append(lines, fmt.Sprintf("%s %v", m.Name, mv.Value))
		}
	}
	return strings.Join(lines, "\n") + "\n"
}

// FormatMetrics formats multiple Prometheus metrics.
func FormatMetrics(metrics []PrometheusMetric) string {
	var parts []string
	for _, m := range metrics {
		parts = append(parts, FormatMetric(m))
	}
	return strings.Join(parts, "\n")
}

// CreateSimpleGauge creates a simple gauge metric with no labels.
func CreateSimpleGauge(name, help string, value float64) PrometheusMetric {
	return PrometheusMetric{
		Name: name,
		Type: "gauge",
		Help: help,
		Values: []MetricValue{
			{Labels: map[string]string{}, Value: value},
		},
	}
}

// CurrentTimestamp returns the current Unix timestamp.
func CurrentTimestamp() int64 {
	return time.Now().Unix()
}

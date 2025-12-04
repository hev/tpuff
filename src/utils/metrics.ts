/**
 * Prometheus metrics utilities for formatting metrics in the text exposition format
 */

export interface MetricLabels {
  [key: string]: string | number;
}

export interface MetricValue {
  labels: MetricLabels;
  value: number;
}

export interface PrometheusMetric {
  name: string;
  type: 'gauge' | 'counter' | 'histogram' | 'summary';
  help: string;
  values: MetricValue[];
}

/**
 * Escapes special characters in Prometheus label values
 * According to Prometheus spec: backslash, double-quote, and line feed must be escaped
 */
export function escapeLabel(value: string | number): string {
  const str = String(value);
  return str
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n');
}

/**
 * Formats a single Prometheus metric in text exposition format
 */
export function formatPrometheusMetric(metric: PrometheusMetric): string {
  let output = '';

  // Add HELP and TYPE comments
  output += `# HELP ${metric.name} ${metric.help}\n`;
  output += `# TYPE ${metric.name} ${metric.type}\n`;

  // Add metric values
  for (const { labels, value } of metric.values) {
    const labelPairs = Object.entries(labels)
      .map(([key, val]) => `${key}="${escapeLabel(val)}"`)
      .join(',');

    if (labelPairs) {
      output += `${metric.name}{${labelPairs}} ${value}\n`;
    } else {
      output += `${metric.name} ${value}\n`;
    }
  }

  return output;
}

/**
 * Formats multiple Prometheus metrics
 */
export function formatPrometheusMetrics(metrics: PrometheusMetric[]): string {
  return metrics.map(formatPrometheusMetric).join('\n');
}

/**
 * Creates a simple gauge metric with a single value and no labels
 */
export function createSimpleGauge(
  name: string,
  help: string,
  value: number
): PrometheusMetric {
  return {
    name,
    type: 'gauge',
    help,
    values: [{ labels: {}, value }]
  };
}

/**
 * Gets current Unix timestamp in seconds
 */
export function getCurrentTimestamp(): number {
  return Math.floor(Date.now() / 1000);
}

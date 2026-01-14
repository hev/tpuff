"""Prometheus metrics utilities for formatting metrics in the text exposition format."""

import time
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class MetricValue:
    """A single metric value with optional labels."""

    labels: dict[str, str | int | float] = field(default_factory=dict)
    value: float = 0.0


@dataclass
class PrometheusMetric:
    """A Prometheus metric with type, help text, and values."""

    name: str
    type: Literal["gauge", "counter", "histogram", "summary"]
    help: str
    values: list[MetricValue] = field(default_factory=list)


def escape_label(value: str | int | float) -> str:
    """Escape special characters in Prometheus label values.

    According to Prometheus spec: backslash, double-quote, and line feed must be escaped.
    """
    s = str(value)
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def format_prometheus_metric(metric: PrometheusMetric) -> str:
    """Format a single Prometheus metric in text exposition format."""
    lines = []

    # Add HELP and TYPE comments
    lines.append(f"# HELP {metric.name} {metric.help}")
    lines.append(f"# TYPE {metric.name} {metric.type}")

    # Add metric values
    for mv in metric.values:
        label_pairs = ",".join(
            f'{key}="{escape_label(val)}"' for key, val in mv.labels.items()
        )

        if label_pairs:
            lines.append(f"{metric.name}{{{label_pairs}}} {mv.value}")
        else:
            lines.append(f"{metric.name} {mv.value}")

    return "\n".join(lines) + "\n"


def format_prometheus_metrics(metrics: list[PrometheusMetric]) -> str:
    """Format multiple Prometheus metrics."""
    return "\n".join(format_prometheus_metric(m) for m in metrics)


def create_simple_gauge(name: str, help_text: str, value: float) -> PrometheusMetric:
    """Create a simple gauge metric with a single value and no labels."""
    return PrometheusMetric(
        name=name,
        type="gauge",
        help=help_text,
        values=[MetricValue(labels={}, value=value)],
    )


def get_current_timestamp() -> int:
    """Get current Unix timestamp in seconds."""
    return int(time.time())

"""Export command for tpuff CLI - Prometheus metrics exporter."""

import json
import signal
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import click
from rich.console import Console

from tpuff.utils.debug import debug_log
from tpuff.utils.metadata_fetcher import (
    NamespaceWithMetadata,
    fetch_namespaces_with_metadata,
    get_encryption_type,
    get_index_status,
    get_unindexed_bytes,
)
from tpuff.utils.metrics import (
    MetricValue,
    PrometheusMetric,
    create_simple_gauge,
    format_prometheus_metrics,
    get_current_timestamp,
)

console = Console()


# Global state for metrics caching
class MetricsCache:
    def __init__(self):
        self.data: str = "# Waiting for first scrape...\n"
        self.last_update: datetime = datetime.now()
        self.error: str | None = None


class RecallCache:
    def __init__(self):
        self.data: dict[str, dict[str, Any]] = {}
        self.last_update: datetime = datetime.fromtimestamp(0)  # Epoch to trigger immediate first fetch


metrics_cache = MetricsCache()
recall_cache = RecallCache()
last_scrape_success = True
last_scrape_duration = 0.0


def generate_prometheus_metrics(namespaces: list[NamespaceWithMetadata]) -> list[PrometheusMetric]:
    """Generate Prometheus metrics from namespace data."""
    # Initialize metrics
    rows_metric = PrometheusMetric(
        name="turbopuffer_namespace_rows",
        type="gauge",
        help="Approximate number of rows in namespace",
        values=[],
    )

    logical_bytes_metric = PrometheusMetric(
        name="turbopuffer_namespace_logical_bytes",
        type="gauge",
        help="Approximate logical storage size in bytes",
        values=[],
    )

    unindexed_bytes_metric = PrometheusMetric(
        name="turbopuffer_namespace_unindexed_bytes",
        type="gauge",
        help="Number of unindexed bytes (0 when index is up-to-date)",
        values=[],
    )

    recall_metric = PrometheusMetric(
        name="turbopuffer_namespace_recall",
        type="gauge",
        help="Average vector recall estimation (0-1 scale)",
        values=[],
    )

    info_metric = PrometheusMetric(
        name="turbopuffer_namespace_info",
        type="gauge",
        help="Namespace information with labels",
        values=[],
    )

    # Populate metrics from namespace data
    for ns in namespaces:
        if not ns.metadata:
            continue  # Skip namespaces without metadata

        labels = {
            "namespace": ns.namespace_id,
            "region": ns.region or "unknown",
            "encryption": get_encryption_type(ns.metadata),
            "index_status": get_index_status(ns.metadata),
        }

        rows_metric.values.append(MetricValue(labels=labels, value=ns.metadata.approx_row_count))
        logical_bytes_metric.values.append(MetricValue(labels=labels, value=ns.metadata.approx_logical_bytes))
        unindexed_bytes_metric.values.append(MetricValue(labels=labels, value=get_unindexed_bytes(ns.metadata)))

        # Add recall metric if recall data is available
        if ns.recall:
            recall_metric.values.append(MetricValue(labels=labels, value=ns.recall.avg_recall))

        info_metric.values.append(
            MetricValue(
                labels={**labels, "updated_at": ns.metadata.updated_at},
                value=1,
            )
        )

    # Collect metrics that have values
    metrics = []
    if rows_metric.values:
        metrics.append(rows_metric)
    if logical_bytes_metric.values:
        metrics.append(logical_bytes_metric)
    if unindexed_bytes_metric.values:
        metrics.append(unindexed_bytes_metric)
    if recall_metric.values:
        metrics.append(recall_metric)
    if info_metric.values:
        metrics.append(info_metric)

    return metrics


def refresh_metrics(
    all_regions: bool,
    region: str | None,
    include_recall: bool,
    recall_interval: int,
) -> None:
    """Refresh the metrics cache."""
    global metrics_cache, recall_cache, last_scrape_success, last_scrape_duration

    start_time = time.time()

    try:
        debug_log("Starting metrics refresh", {
            "all_regions": all_regions,
            "region": region,
            "include_recall": include_recall,
        })

        # Determine if we should refresh recall data
        time_since_last_recall = time.time() - recall_cache.last_update.timestamp()
        should_refresh_recall = include_recall and (time_since_last_recall >= recall_interval)

        if should_refresh_recall:
            debug_log("Refreshing recall data", {
                "time_since_last_recall": time_since_last_recall,
                "recall_interval": recall_interval,
            })

        # Fetch namespaces with metadata
        namespaces = fetch_namespaces_with_metadata(
            all_regions=all_regions,
            region=region,
            include_recall=should_refresh_recall,
        )

        debug_log("Fetched namespaces", {
            "count": len(namespaces),
            "refreshed_recall": should_refresh_recall,
        })

        # Update recall cache if we refreshed it
        if should_refresh_recall:
            recall_cache.data.clear()
            for ns in namespaces:
                if ns.recall:
                    recall_cache.data[ns.namespace_id] = {
                        "recall": ns.recall,
                        "region": ns.region,
                    }
            recall_cache.last_update = datetime.now()
            debug_log("Updated recall cache", {"cached_namespaces": len(recall_cache.data)})
        elif include_recall:
            # Merge cached recall data into namespaces
            for ns in namespaces:
                cached = recall_cache.data.get(ns.namespace_id)
                if cached and cached.get("region") == ns.region:
                    ns.recall = cached.get("recall")
            debug_log("Merged cached recall data", {"cached_namespaces": len(recall_cache.data)})

        # Generate Prometheus metrics
        metrics = generate_prometheus_metrics(namespaces)

        # Add exporter self-monitoring metrics
        scrape_duration = time.time() - start_time
        last_scrape_duration = scrape_duration
        last_scrape_success = True

        metrics.append(
            create_simple_gauge(
                "turbopuffer_exporter_scrape_duration_seconds",
                "Time taken to fetch metrics from Turbopuffer API",
                scrape_duration,
            )
        )

        metrics.append(
            create_simple_gauge(
                "turbopuffer_exporter_last_scrape_timestamp_seconds",
                "Unix timestamp of last successful scrape",
                get_current_timestamp(),
            )
        )

        # Format all metrics
        metrics_text = format_prometheus_metrics(metrics)

        # Update cache
        metrics_cache.data = metrics_text
        metrics_cache.last_update = datetime.now()
        metrics_cache.error = None

        debug_log("Metrics refresh completed", {
            "duration": scrape_duration,
            "namespace_count": len(namespaces),
        })

    except Exception as e:
        error_message = str(e)
        console.print(f"[red]Error refreshing metrics: {error_message}[/red]")
        debug_log("Metrics refresh failed", {"error": error_message})

        last_scrape_success = False

        # Keep serving old metrics with error comment
        error_comment = (
            f"# Error refreshing metrics: {error_message}\n"
            f"# Last successful update: {metrics_cache.last_update.isoformat()}\n\n"
        )
        metrics_cache.error = error_message
        metrics_cache.data = error_comment + metrics_cache.data


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Prometheus metrics."""

    server_options: dict[str, Any] = {}

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:
        if self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics_cache.data.encode())

        elif self.path == "/health":
            health = {
                "status": "ok",
                "lastUpdate": metrics_cache.last_update.isoformat(),
                "error": metrics_cache.error,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health, indent=2).encode())

        elif self.path == "/":
            options = self.server_options
            html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Turbopuffer Prometheus Exporter</title>
  <style>
    body {{ font-family: sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
    h1 {{ color: #333; }}
    a {{ color: #0066cc; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    code {{ background: #eee; padding: 2px 6px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>Turbopuffer Prometheus Exporter</h1>
  <div class="info">
    <p><strong>Status:</strong> Running</p>
    <p><strong>Last Update:</strong> {metrics_cache.last_update.isoformat()}</p>
    <p><strong>Refresh Interval:</strong> {options.get('interval', 60)}s</p>
    <p><strong>Region Mode:</strong> {'All regions' if options.get('all_regions') else options.get('region') or 'Default'}</p>
    <p><strong>Recall Metrics:</strong> {'enabled (refresh: ' + str(options.get('recall_interval', 3600)) + 's)' if options.get('include_recall') else 'disabled'}</p>
  </div>
  <h2>Endpoints</h2>
  <ul>
    <li><a href="/metrics">/metrics</a> - Prometheus metrics endpoint</li>
    <li><a href="/health">/health</a> - Health check endpoint</li>
  </ul>
  <h2>Example Prometheus Configuration</h2>
  <pre><code>scrape_configs:
  - job_name: 'turbopuffer'
    scrape_interval: {options.get('interval', 60)}s
    static_configs:
      - targets: ['localhost:{options.get('port', 9876)}']</code></pre>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())

        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")


def start_http_server(
    port: int,
    region: str | None,
    all_regions: bool,
    interval: int,
    timeout: int,
    include_recall: bool,
    recall_interval: int,
) -> None:
    """Start the HTTP server for Prometheus metrics."""
    # Store options for the handler
    MetricsHandler.server_options = {
        "port": port,
        "region": region,
        "all_regions": all_regions,
        "interval": interval,
        "include_recall": include_recall,
        "recall_interval": recall_interval,
    }

    # Perform initial metrics fetch
    console.print("[dim]Performing initial metrics fetch...[/dim]")
    refresh_metrics(all_regions, region, include_recall, recall_interval)

    # Start background refresh thread
    stop_event = threading.Event()

    def refresh_loop():
        while not stop_event.is_set():
            stop_event.wait(interval)
            if not stop_event.is_set():
                refresh_metrics(all_regions, region, include_recall, recall_interval)

    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()

    # Create HTTP server
    server = HTTPServer(("", port), MetricsHandler)

    # Graceful shutdown handler
    def shutdown_handler(signum: int, frame: Any) -> None:
        signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        console.print(f"\n[yellow]Received {signal_name}, shutting down gracefully...[/yellow]")
        stop_event.set()
        server.shutdown()
        console.print("[dim]HTTP server closed[/dim]")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Print startup message
    console.print("[green]✓ Turbopuffer Prometheus exporter running[/green]")
    console.print(f"[dim]  Port:           {port}[/dim]")
    console.print(f"[dim]  Refresh:        {interval}s[/dim]")
    console.print(f"[dim]  Region mode:    {'All regions' if all_regions else region or 'Default'}[/dim]")
    if include_recall:
        console.print(f"[yellow]  Recall:         enabled (refresh: {recall_interval}s)[/yellow]")
        console.print("[dim]                  Note: Recall estimation runs queries and incurs costs[/dim]")
    else:
        console.print("[dim]  Recall:         disabled (use --include-recall to enable)[/dim]")
    console.print("\n[dim]  Endpoints:[/dim]")
    console.print(f"[dim]    http://localhost:{port}/metrics[/dim]")
    console.print(f"[dim]    http://localhost:{port}/health[/dim]")
    console.print(f"[dim]    http://localhost:{port}/[/dim]")
    console.print("\n[dim]  Press Ctrl+C to stop[/dim]\n")

    # Start server
    try:
        server.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e):
            console.print(f"[red]Error: Port {port} is already in use[/red]")
            console.print("[dim]Please choose a different port with --port <number>[/dim]")
        else:
            console.print(f"[red]Server error: {e}[/red]")
        sys.exit(1)


@click.command("export", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-p", "--port", default=9876, type=int, help="HTTP server port")
@click.option("-r", "--region", help="Query specific region (default: TURBOPUFFER_REGION env)")
@click.option("-A", "--all-regions", is_flag=True, help="Query all Turbopuffer regions")
@click.option("-i", "--interval", default=60, type=int, help="Metric refresh interval in seconds")
@click.option("-t", "--timeout", default=30, type=int, help="API request timeout per region in seconds")
@click.option("--include-recall", is_flag=True, help="Include recall estimation metrics (runs queries, incurs costs)")
@click.option("--recall-interval", default=3600, type=int, help="Recall estimation refresh interval in seconds")
@click.pass_context
def export(
    ctx: click.Context,
    port: int,
    region: str | None,
    all_regions: bool,
    interval: int,
    timeout: int,
    include_recall: bool,
    recall_interval: int,
) -> None:
    """Run Prometheus exporter for Turbopuffer namespace metrics."""
    # Validate options
    if port < 1 or port > 65535:
        console.print("[red]Error: Port must be a number between 1 and 65535[/red]")
        sys.exit(1)

    if interval < 1:
        console.print("[red]Error: Interval must be a positive number[/red]")
        sys.exit(1)

    if timeout < 1:
        console.print("[red]Error: Timeout must be a positive number[/red]")
        sys.exit(1)

    if recall_interval < 1:
        console.print("[red]Error: Recall interval must be a positive number[/red]")
        sys.exit(1)

    # Validate mutual exclusivity of --all-regions and --region
    if all_regions and region:
        console.print("[red]Error: Cannot use both --all-regions and --region flags together[/red]")
        console.print("[dim]Please use either --all-regions to query all regions, or --region to specify a single region[/dim]")
        sys.exit(1)

    try:
        start_http_server(
            port=port,
            region=region,
            all_regions=all_regions,
            interval=interval,
            timeout=timeout,
            include_recall=include_recall,
            recall_interval=recall_interval,
        )
    except Exception as e:
        console.print(f"[red]Error starting exporter: {e}[/red]")
        sys.exit(1)

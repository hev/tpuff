"""List command for tpuff CLI."""

import json
import sys
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from tpuff.client import get_namespace
from tpuff.utils.debug import debug_log
from tpuff.utils.metadata_fetcher import (
    NamespaceWithMetadata,
    fetch_namespaces_with_metadata,
)
from tpuff.utils.output import is_plain, print_table_plain, status_print

console = Console()


def format_bytes(bytes_count: int) -> str:
    """Format bytes into human readable string."""
    if bytes_count == 0:
        return "0 B"
    k = 1024
    sizes = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_count >= k and i < len(sizes) - 1:
        bytes_count /= k
        i += 1
    return f"{bytes_count:.2f} {sizes[i]}"


def format_updated_at(timestamp: str | datetime | None, plain: bool = False) -> str:
    """Format timestamp smartly: time if today, date otherwise."""
    if timestamp is None:
        return "N/A" if plain else "[dim]N/A[/dim]"

    try:
        # Handle datetime objects directly
        if isinstance(timestamp, datetime):
            date = timestamp
        else:
            date = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))

        now = datetime.now(date.tzinfo)

        is_today = (
            date.date() == now.date()
            if date.tzinfo
            else date.date() == datetime.now().date()
        )

        if is_today:
            return date.strftime("%-I:%M %p").lower()
        else:
            return date.strftime("%b %-d, %Y")
    except Exception:
        if timestamp:
            return str(timestamp)
        return "N/A" if plain else "[dim]N/A[/dim]"


def format_recall(recall_data, plain: bool = False) -> str:
    """Format recall as a color-coded percentage."""
    if not recall_data:
        return "N/A" if plain else "[dim]N/A[/dim]"

    percentage = recall_data.avg_recall * 100
    display_value = f"{percentage:.1f}%"

    if plain:
        return display_value

    if recall_data.avg_recall > 0.95:
        return f"[green]{display_value}[/green]"
    elif recall_data.avg_recall > 0.8:
        return f"[yellow]{display_value}[/yellow]"
    else:
        return f"[red]{display_value}[/red]"


def extract_vector_info(schema: dict) -> dict | None:
    """Extract vector attribute name and dimensions from namespace schema.

    Args:
        schema: The namespace schema.

    Returns:
        Dict with attributeName and dimensions, or None if no vector found.
    """
    import re

    for attr_name, attr_config in schema.items():
        type_str = attr_config if isinstance(attr_config, str) else attr_config.get("type")

        if type_str and isinstance(type_str, str):
            # Match patterns like [384]f32, [1536]f16, etc.
            match = re.match(r"\[(\d+)\]f(?:16|32)", type_str)
            if match:
                return {
                    "attributeName": attr_name,
                    "dimensions": int(match.group(1)),
                }

    return None


def display_namespace_documents(
    ctx: click.Context, namespace: str, top_k: int, region: str | None = None
) -> None:
    """List documents in a specific namespace."""
    plain = is_plain(ctx)
    ns = get_namespace(namespace, region)

    status_print(
        ctx,
        f"\n[bold]Querying namespace: {namespace} (top {top_k} results)[/bold]\n",
        console,
    )

    # Get namespace metadata to extract schema
    metadata = ns.metadata()

    # Extract schema - access the dict attribute from model_dump()
    schema_dict = metadata.model_dump().get("schema", {})

    # Extract vector info from schema
    vector_info = extract_vector_info(schema_dict)

    if not vector_info:
        console.print("[red]Error: No vector attribute found in namespace schema[/red]")
        sys.exit(1)

    status_print(
        ctx,
        f"[dim]Using {vector_info['dimensions']}-dimensional zero vector for query[/dim]\n",
        console,
    )

    # Create zero vector
    zero_vector = [0.0] * vector_info["dimensions"]

    query_params = {
        "rank_by": [vector_info["attributeName"], "ANN", zero_vector],
        "top_k": top_k,
        "exclude_attributes": [vector_info["attributeName"]],
    }

    # Debug: Log query parameters
    debug_log("Query Parameters", query_params)

    # Query the namespace
    result = ns.query(**query_params)

    # Debug: Log API response
    debug_log("Query Response", result)

    # Extract rows from the response
    rows = result.rows if hasattr(result, "rows") else []

    if not rows:
        console.print("No documents found in namespace")
        return

    status_print(ctx, f"[bold]Found {len(rows)} document(s):[/bold]\n", console)

    # Collect row data
    table_rows = []
    for row in rows:
        # Get the row as a dict using model_dump() or fallback
        if hasattr(row, "model_dump"):
            row_dict = row.model_dump()
        elif hasattr(row, "to_dict"):
            row_dict = row.to_dict()
        else:
            row_dict = {"id": getattr(row, "id", "N/A")}

        row_id = row_dict.get("id", getattr(row, "id", "N/A"))

        # Collect all attributes except system fields
        contents = {}
        exclude_keys = {"id", "vector", "$dist", "dist", "attributes"}
        for key, value in row_dict.items():
            if key not in exclude_keys and not key.startswith("_"):
                contents[key] = value

        contents_str = json.dumps(contents, default=str)
        table_rows.append([str(row_id), contents_str])

    if plain:
        print_table_plain(["ID", "Contents"], table_rows)
    else:
        table = Table(show_header=True, header_style="cyan")
        table.add_column("ID")
        table.add_column("Contents")
        for r in table_rows:
            table.add_row(*r)
        console.print(table)

    # Show performance info if available
    if hasattr(result, "performance") and result.performance:
        status_print(
            ctx,
            f"\n[dim]Query took {result.performance.query_execution_ms:.2f}ms[/dim]",
            console,
        )


def display_namespaces(
    ctx: click.Context,
    all_regions: bool = False,
    region: str | None = None,
    include_recall: bool = False,
) -> None:
    """List all namespaces."""
    plain = is_plain(ctx)
    namespaces_with_metadata = fetch_namespaces_with_metadata(
        all_regions=all_regions,
        region=region,
        include_recall=include_recall,
    )

    if not namespaces_with_metadata:
        console.print("No namespaces found")
        return

    # Sort by updated_at in descending order (most recent first)
    def sort_key(item: NamespaceWithMetadata):
        if not item.metadata:
            return datetime.min
        try:
            updated_at = item.metadata.updated_at
            if isinstance(updated_at, datetime):
                return updated_at
            return datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        except Exception:
            return datetime.min

    namespaces_with_metadata.sort(key=sort_key, reverse=True)

    if plain:
        # Plain mode: pipe-delimited for scripts
        headers = ["Namespace"]
        if all_regions:
            headers.append("Region")
        headers.extend(["Rows", "Size", "Updated"])
        if include_recall:
            headers.append("Recall")

        table_rows = []
        for item in namespaces_with_metadata:
            if item.metadata:
                row = [item.namespace_id]
                if all_regions:
                    row.append(item.region or "")
                row.extend([
                    f"{item.metadata.approx_row_count:,}",
                    format_bytes(item.metadata.approx_logical_bytes),
                    format_updated_at(item.metadata.updated_at, plain=True),
                ])
                if include_recall:
                    row.append(format_recall(item.recall, plain=True))
            else:
                row = [item.namespace_id]
                if all_regions:
                    row.append(item.region or "")
                row.extend(["N/A", "N/A", "N/A"])
                if include_recall:
                    row.append("N/A")
            table_rows.append(row)

        print_table_plain(headers, table_rows)
    else:
        # Human mode: lean ll-style output
        for item in namespaces_with_metadata:
            if item.metadata:
                rows = f"{item.metadata.approx_row_count:,} rows"
                size = format_bytes(item.metadata.approx_logical_bytes)
                date = format_updated_at(item.metadata.updated_at)
                region_part = f"  [dim]{item.region}[/dim]" if all_regions and item.region else ""
                recall_part = f"  {format_recall(item.recall)}" if include_recall else ""
                console.print(
                    f"[bold]{item.namespace_id}[/bold]  "
                    f"[cyan]{rows:>12}[/cyan]  "
                    f"[dim]{size:>10}[/dim]{region_part}{recall_part}  "
                    f"[dim]{date}[/dim]"
                )
            else:
                region_part = f"  [dim]{item.region}[/dim]" if all_regions and item.region else ""
                console.print(
                    f"[bold]{item.namespace_id}[/bold]  "
                    f"[dim]{'N/A':>12}[/dim]  "
                    f"[dim]{'N/A':>10}[/dim]{region_part}  "
                    f"[dim]N/A[/dim]"
                )


@click.command("list", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--namespace", help="Namespace to list documents from")
@click.option("-k", "--top-k", default=10, type=int, help="Number of documents to return")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.option("-A", "--all", "all_regions", is_flag=True, help="Query all regions")
@click.option("--recall", "include_recall", is_flag=True, help="Include recall estimation (slower)")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    namespace: str | None,
    top_k: int,
    region: str | None,
    all_regions: bool,
    include_recall: bool,
) -> None:
    """List namespaces or documents in a namespace."""
    # When querying all regions, include recall by default
    if all_regions:
        include_recall = True

    # Validate that --all and --region are not used together
    if all_regions and region:
        console.print("[red]Error: Cannot use both --all and --region flags together[/red]")
        console.print(
            "[dim]Please use either --all to query all regions, or --region to specify a single region[/dim]"
        )
        sys.exit(1)

    try:
        if namespace:
            # List documents in namespace
            if all_regions:
                console.print(
                    "[red]Error: --all flag is not supported when querying a specific namespace[/red]"
                )
                console.print(
                    "[dim]Please specify a region with -r <region> to query documents in a namespace[/dim]"
                )
                sys.exit(1)

            display_namespace_documents(ctx, namespace, top_k, region)
        else:
            # List all namespaces
            display_namespaces(ctx, all_regions, region, include_recall)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

"""List command for tpuff CLI."""

import json
import sys
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from tpuff.client import get_namespace, get_turbopuffer_client
from tpuff.utils.debug import debug_log
from tpuff.utils.metadata_fetcher import (
    NamespaceWithMetadata,
    fetch_namespaces_with_metadata,
    get_index_status,
    get_unindexed_bytes,
)


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


def format_updated_at(timestamp: str) -> str:
    """Format timestamp smartly: time if today, date otherwise."""
    try:
        date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
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
        return timestamp


def format_recall(recall_data) -> str:
    """Format recall as a color-coded percentage."""
    if not recall_data:
        return "[dim]N/A[/dim]"

    percentage = recall_data.avg_recall * 100
    display_value = f"{percentage:.1f}%"

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
    namespace: str, top_k: int, region: str | None = None
) -> None:
    """List documents in a specific namespace."""
    ns = get_namespace(namespace, region)

    console.print(f"\n[bold]Querying namespace: {namespace} (top {top_k} results)[/bold]\n")

    # Get namespace metadata to extract schema
    metadata = ns.metadata()

    # Extract schema - access the dict attribute from model_dump()
    schema_dict = metadata.model_dump().get("schema", {})

    # Extract vector info from schema
    vector_info = extract_vector_info(schema_dict)

    if not vector_info:
        console.print("[red]Error: No vector attribute found in namespace schema[/red]")
        sys.exit(1)

    console.print(
        f"[dim]Using {vector_info['dimensions']}-dimensional zero vector for query[/dim]\n"
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

    console.print(f"[bold]Found {len(rows)} document(s):[/bold]\n")

    # Create table for results
    table = Table(show_header=True, header_style="cyan")
    table.add_column("ID")
    table.add_column("Contents")

    # Add rows to table
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

        # Stringify and truncate contents
        contents_str = json.dumps(contents, default=str)
        max_length = 80
        display_contents = (
            contents_str[:max_length] + "..." if len(contents_str) > max_length else contents_str
        )

        table.add_row(str(row_id), display_contents)

    console.print(table)

    # Show performance info if available
    if hasattr(result, "performance") and result.performance:
        console.print(
            f"\n[dim]Query took {result.performance.query_execution_ms:.2f}ms[/dim]"
        )


def display_namespaces(
    all_regions: bool = False,
    region: str | None = None,
    include_recall: bool = False,
) -> None:
    """List all namespaces."""
    namespaces_with_metadata = fetch_namespaces_with_metadata(
        all_regions=all_regions,
        region=region,
        include_recall=include_recall,
    )

    if not namespaces_with_metadata:
        console.print("No namespaces found")
        return

    console.print(f"\n[bold]Found {len(namespaces_with_metadata)} namespace(s):[/bold]\n")

    # Sort by updated_at in descending order (most recent first)
    def sort_key(item: NamespaceWithMetadata):
        if not item.metadata:
            return datetime.min
        try:
            return datetime.fromisoformat(item.metadata.updated_at.replace("Z", "+00:00"))
        except Exception:
            return datetime.min

    namespaces_with_metadata.sort(key=sort_key, reverse=True)

    # Create table with conditional region and recall columns
    table = Table(show_header=True, header_style="cyan")
    table.add_column("Namespace")
    if all_regions:
        table.add_column("Region")
    table.add_column("Rows")
    table.add_column("Logical Bytes")
    table.add_column("Index Status")
    table.add_column("Unindexed Bytes")
    if include_recall:
        table.add_column("Recall")
    table.add_column("Updated")

    # Add rows to table
    for item in namespaces_with_metadata:
        if item.metadata:
            index_status = get_index_status(item.metadata)
            index_status_display = (
                "[green]up-to-date[/green]"
                if index_status == "up-to-date"
                else "[red]updating[/red]"
            )

            unindexed = get_unindexed_bytes(item.metadata)
            unindexed_display = (
                f"[red]{format_bytes(unindexed)}[/red]"
                if unindexed > 0
                else format_bytes(0)
            )

            row = [f"[bold]{item.namespace_id}[/bold]"]
            if all_regions and item.region:
                row.append(f"[dim]{item.region}[/dim]")
            row.extend([
                f"{item.metadata.approx_row_count:,}",
                format_bytes(item.metadata.approx_logical_bytes),
                index_status_display,
                unindexed_display,
            ])
            if include_recall:
                row.append(format_recall(item.recall))
            row.append(format_updated_at(item.metadata.updated_at))

            table.add_row(*row)
        else:
            row = [f"[bold]{item.namespace_id}[/bold]"]
            if all_regions and item.region:
                row.append(f"[dim]{item.region}[/dim]")
            row.extend(["[dim]N/A[/dim]"] * 4)
            if include_recall:
                row.append("[dim]N/A[/dim]")
            row.append("[dim]N/A[/dim]")

            table.add_row(*row)

    console.print(table)


@click.command("list")
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

            display_namespace_documents(namespace, top_k, region)
        else:
            # List all namespaces
            display_namespaces(all_regions, region, include_recall)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

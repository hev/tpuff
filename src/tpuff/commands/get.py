"""Get command for tpuff CLI."""

import json
import sys

import click
from rich.console import Console

from tpuff.client import get_namespace
from tpuff.utils.debug import debug_log


console = Console()


@click.command("get")
@click.argument("id")
@click.option("-n", "--namespace", required=True, help="Namespace to query")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.pass_context
def get(
    ctx: click.Context,
    id: str,
    namespace: str,
    region: str | None,
) -> None:
    """Get a document by ID from a namespace."""
    try:
        console.print(f"\n[bold]Querying document with ID: {id} from namespace: {namespace}[/bold]\n")

        # Get namespace reference
        ns = get_namespace(namespace, region)

        # Query with id filter
        query_params = {
            "filters": ["id", "Eq", id],
            "top_k": 1,
            "include_attributes": True,
        }

        # Debug: Log query parameters
        debug_log("Query Parameters", query_params)

        result = ns.query(**query_params)

        # Debug: Log API response
        debug_log("Query Response", result)

        # Extract rows from the response
        rows = result.rows if hasattr(result, "rows") else []

        # Check if document was found
        if not rows:
            console.print("[yellow]Document not found[/yellow]")
            sys.exit(1)

        # Get the document
        doc = rows[0]

        # Convert to dict for display
        if hasattr(doc, "model_dump"):
            doc_dict = doc.model_dump()
        elif hasattr(doc, "to_dict"):
            doc_dict = doc.to_dict()
        else:
            doc_dict = {"id": getattr(doc, "id", "N/A")}

        # Display document
        console.print("[cyan]Document:[/cyan]")
        console.print(json.dumps(doc_dict, indent=2, default=str))

        # Show performance info
        if hasattr(result, "performance") and result.performance:
            console.print(
                f"\n[dim]Query took {result.performance.query_execution_ms:.2f}ms[/dim]"
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

"""Schema management commands for tpuff CLI."""

import json
import sys

import click
from rich.console import Console

from tpuff.client import get_namespace


console = Console()


@click.group("schema", context_settings={"help_option_names": ["-h", "--help"]})
def schema() -> None:
    """Manage namespace schemas."""
    pass


@schema.command("get", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--namespace", required=True, help="Namespace to get schema from")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.option("--raw", is_flag=True, help="Output raw JSON without formatting (for piping)")
@click.pass_context
def schema_get(
    ctx: click.Context,
    namespace: str,
    region: str | None,
    raw: bool,
) -> None:
    """Display the schema for a namespace."""
    try:
        ns = get_namespace(namespace, region)
        metadata = ns.metadata()

        # Extract schema from metadata
        schema_data = metadata.schema if hasattr(metadata, "schema") else {}

        if not schema_data:
            if raw:
                print("{}")
            else:
                console.print(f"[yellow]No schema found for namespace: {namespace}[/yellow]")
            return

        # Convert schema to serializable format
        schema_dict = {}
        for attr_name, attr_type in schema_data.items():
            # Handle both simple string types and complex type objects
            if hasattr(attr_type, "model_dump"):
                schema_dict[attr_name] = attr_type.model_dump()
            elif hasattr(attr_type, "to_dict"):
                schema_dict[attr_name] = attr_type.to_dict()
            else:
                schema_dict[attr_name] = str(attr_type)

        if raw:
            print(json.dumps(schema_dict))
        else:
            console.print(f"\n[bold]Schema for namespace: {namespace}[/bold]\n")
            console.print(json.dumps(schema_dict, indent=2))

    except Exception as e:
        if raw:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
        else:
            console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

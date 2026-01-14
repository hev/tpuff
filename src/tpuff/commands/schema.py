"""Schema management commands for tpuff CLI."""

import json
import sys
from dataclasses import dataclass, field

import click
from rich.console import Console

from tpuff.client import get_namespace

console = Console()


@dataclass
class SchemaDiff:
    """Result of comparing two schemas."""

    unchanged: dict[str, str] = field(default_factory=dict)
    additions: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, tuple[str, str]] = field(default_factory=dict)  # attr -> (old_type, new_type)

    @property
    def has_conflicts(self) -> bool:
        """Check if there are any type conflicts."""
        return len(self.conflicts) > 0

    @property
    def has_changes(self) -> bool:
        """Check if there are any additions or conflicts."""
        return len(self.additions) > 0 or len(self.conflicts) > 0


def normalize_schema_type(attr_type: object) -> str:
    """Normalize a schema type to a comparable string representation.

    Handles both simple string types and complex type objects from turbopuffer.
    """
    if hasattr(attr_type, "model_dump"):
        # Pydantic model - convert to JSON string for comparison
        return json.dumps(attr_type.model_dump(), sort_keys=True)
    elif hasattr(attr_type, "to_dict"):
        return json.dumps(attr_type.to_dict(), sort_keys=True)
    elif isinstance(attr_type, dict):
        return json.dumps(attr_type, sort_keys=True)
    else:
        return str(attr_type)


def schema_type_for_display(attr_type: object) -> str:
    """Convert a schema type to a human-readable display string."""
    if hasattr(attr_type, "model_dump"):
        dumped = attr_type.model_dump()
        # For complex types, show the full dict; for simple, just the string
        if isinstance(dumped, dict) and len(dumped) == 1 and "type" in dumped:
            return str(dumped["type"])
        return json.dumps(dumped)
    elif hasattr(attr_type, "to_dict"):
        return json.dumps(attr_type.to_dict())
    elif isinstance(attr_type, dict):
        if len(attr_type) == 1 and "type" in attr_type:
            return str(attr_type["type"])
        return json.dumps(attr_type)
    else:
        return str(attr_type)


def display_schema_diff(diff: SchemaDiff, namespace: str) -> None:
    """Display a schema diff with Rich formatting.

    Args:
        diff: The computed schema diff
        namespace: The namespace name (for header)
    """
    console.print(f"\n[bold]Schema changes for namespace: {namespace}[/bold]\n")

    if not diff.has_changes and not diff.unchanged:
        console.print("[dim]No schema attributes[/dim]")
        return

    # Sort all attributes for consistent output
    all_attrs = sorted(
        set(diff.unchanged.keys()) | set(diff.additions.keys()) | set(diff.conflicts.keys())
    )

    for attr in all_attrs:
        if attr in diff.unchanged:
            # Unchanged attribute
            console.print(f"  {attr}: {diff.unchanged[attr]}")
        elif attr in diff.additions:
            # New attribute
            console.print(f"[green]+{attr}: {diff.additions[attr]}[/green]  [dim](new)[/dim]")
        elif attr in diff.conflicts:
            # Type conflict
            old_type, new_type = diff.conflicts[attr]
            console.print(
                f"[red]!{attr}: {old_type} -> {new_type}[/red]  "
                f"[dim](type change not allowed)[/dim]"
            )

    console.print()  # Blank line at end


def compute_schema_diff(
    current_schema: dict[str, object] | None,
    new_schema: dict[str, object],
) -> SchemaDiff:
    """Compute the difference between current and new schemas.

    Args:
        current_schema: The existing schema (None if namespace doesn't exist)
        new_schema: The schema to be applied

    Returns:
        SchemaDiff with unchanged, additions, and conflicts
    """
    diff = SchemaDiff()

    if current_schema is None:
        current_schema = {}

    # Normalize current schema for comparison
    current_normalized = {
        attr: normalize_schema_type(attr_type)
        for attr, attr_type in current_schema.items()
    }

    # Compare each attribute in the new schema
    for attr, new_type in new_schema.items():
        new_type_normalized = normalize_schema_type(new_type)
        new_type_display = schema_type_for_display(new_type)

        if attr not in current_normalized:
            # New attribute
            diff.additions[attr] = new_type_display
        elif current_normalized[attr] == new_type_normalized:
            # Unchanged
            diff.unchanged[attr] = new_type_display
        else:
            # Type conflict
            old_type_display = schema_type_for_display(current_schema[attr])
            diff.conflicts[attr] = (old_type_display, new_type_display)

    return diff


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

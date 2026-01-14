"""Schema management commands for tpuff CLI."""

import json
import re
import sys
from dataclasses import dataclass, field

import click
from rich.console import Console
from rich.table import Table

from tpuff.client import get_namespace, get_turbopuffer_client

console = Console()

# Valid simple schema types
VALID_SIMPLE_TYPES = {"string", "uint64", "uuid", "bool"}

# Regex for vector types: [dims]f32 or [dims]f16
VECTOR_TYPE_PATTERN = re.compile(r"^\[\d+\]f(16|32)$")

# Valid keys for complex type objects
VALID_TYPE_KEYS = {"type", "full_text_search", "regex_index", "filterable"}


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


def validate_schema_type(attr_name: str, attr_type: object) -> list[str]:
    """Validate a single schema attribute type.

    Args:
        attr_name: The attribute name (for error messages)
        attr_type: The attribute type to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    if isinstance(attr_type, str):
        # Simple string type
        if attr_type in VALID_SIMPLE_TYPES:
            return []
        if VECTOR_TYPE_PATTERN.match(attr_type):
            return []
        errors.append(
            f"Attribute '{attr_name}': invalid type '{attr_type}'. "
            f"Valid types: {', '.join(sorted(VALID_SIMPLE_TYPES))}, or vector format [dims]f32/f16"
        )
    elif isinstance(attr_type, dict):
        # Complex type object
        if "type" not in attr_type:
            errors.append(f"Attribute '{attr_name}': complex type object must have a 'type' key")
        else:
            base_type = attr_type["type"]
            if not isinstance(base_type, str):
                errors.append(f"Attribute '{attr_name}': 'type' must be a string")
            elif base_type not in VALID_SIMPLE_TYPES and not VECTOR_TYPE_PATTERN.match(base_type):
                errors.append(
                    f"Attribute '{attr_name}': invalid base type '{base_type}'. "
                    f"Valid types: {', '.join(sorted(VALID_SIMPLE_TYPES))}, or vector format [dims]f32/f16"
                )

        # Check for unknown keys
        unknown_keys = set(attr_type.keys()) - VALID_TYPE_KEYS
        if unknown_keys:
            errors.append(
                f"Attribute '{attr_name}': unknown keys {sorted(unknown_keys)}. "
                f"Valid keys: {', '.join(sorted(VALID_TYPE_KEYS))}"
            )

        # Validate specific option types
        if "full_text_search" in attr_type and not isinstance(attr_type["full_text_search"], bool):
            errors.append(f"Attribute '{attr_name}': 'full_text_search' must be a boolean")
        if "regex_index" in attr_type and not isinstance(attr_type["regex_index"], bool):
            errors.append(f"Attribute '{attr_name}': 'regex_index' must be a boolean")
        if "filterable" in attr_type and not isinstance(attr_type["filterable"], bool):
            errors.append(f"Attribute '{attr_name}': 'filterable' must be a boolean")
    else:
        errors.append(
            f"Attribute '{attr_name}': type must be a string or object, got {type(attr_type).__name__}"
        )

    return errors


def validate_schema(schema_data: dict) -> list[str]:
    """Validate a complete schema dictionary.

    Args:
        schema_data: The schema dictionary to validate

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    for attr_name, attr_type in schema_data.items():
        if not isinstance(attr_name, str):
            errors.append(f"Attribute name must be a string, got {type(attr_name).__name__}")
            continue
        if not attr_name:
            errors.append("Attribute name cannot be empty")
            continue

        errors.extend(validate_schema_type(attr_name, attr_type))

    return errors


def load_schema_file(file_path: str) -> dict[str, object]:
    """Load and validate a schema from a JSON file.

    Args:
        file_path: Path to the JSON schema file

    Returns:
        The parsed schema dictionary

    Raises:
        click.ClickException: If file cannot be read, parsed, or is invalid
    """
    try:
        with open(file_path) as f:
            schema_data = json.load(f)
    except FileNotFoundError:
        raise click.ClickException(f"Schema file not found: {file_path}")
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON in schema file: {e}")

    if not isinstance(schema_data, dict):
        raise click.ClickException("Schema file must contain a JSON object")

    # Validate schema structure and types
    errors = validate_schema(schema_data)
    if errors:
        error_msg = "Invalid schema:\n  " + "\n  ".join(errors)
        raise click.ClickException(error_msg)

    return schema_data


def get_current_schema(ns) -> dict[str, object] | None:
    """Get the current schema from a namespace.

    Args:
        ns: The turbopuffer namespace object

    Returns:
        The schema dict, or None if namespace doesn't exist/has no schema
    """
    try:
        metadata = ns.metadata()
        schema_data = metadata.schema if hasattr(metadata, "schema") else None
        if not schema_data:
            return None

        # Convert to plain dict for comparison
        result = {}
        for attr_name, attr_type in schema_data.items():
            if hasattr(attr_type, "model_dump"):
                result[attr_name] = attr_type.model_dump()
            elif hasattr(attr_type, "to_dict"):
                result[attr_name] = attr_type.to_dict()
            else:
                result[attr_name] = str(attr_type)
        return result
    except Exception:
        # Namespace doesn't exist or other error
        return None


def list_namespaces_by_prefix(prefix: str, region: str | None) -> list[str]:
    """List namespaces matching a prefix.

    Args:
        prefix: The prefix to match against namespace names
        region: Optional region override

    Returns:
        List of namespace IDs matching the prefix
    """
    client = get_turbopuffer_client(region)
    namespaces = list(client.namespaces())
    return sorted([ns.id for ns in namespaces if ns.id.startswith(prefix)])


def list_all_namespaces(region: str | None) -> list[str]:
    """List all namespaces.

    Args:
        region: Optional region override

    Returns:
        List of all namespace IDs
    """
    client = get_turbopuffer_client(region)
    namespaces = list(client.namespaces())
    return sorted([ns.id for ns in namespaces])


@dataclass
class BatchApplyResult:
    """Result of applying schema to a single namespace in a batch operation."""

    namespace: str
    success: bool
    additions: int = 0
    conflicts: int = 0
    error: str | None = None


def display_batch_summary(results: list[BatchApplyResult], dry_run: bool = False) -> None:
    """Display a summary table of batch apply results.

    Args:
        results: List of BatchApplyResult objects
        dry_run: Whether this was a dry run
    """
    table = Table(show_header=True, header_style="cyan")
    table.add_column("Namespace")
    table.add_column("Changes")
    table.add_column("Status")

    for result in results:
        if result.conflicts > 0:
            changes = f"+{result.additions} attributes [red]({result.conflicts} conflict(s))[/red]"
            status = "[red]blocked[/red]"
        elif result.error:
            changes = "[dim]N/A[/dim]"
            status = f"[red]error: {result.error}[/red]"
        elif result.additions == 0:
            changes = "[dim]no changes[/dim]"
            status = "[green]up-to-date[/green]" if not dry_run else "[dim]would skip[/dim]"
        else:
            changes = f"+{result.additions} attribute(s)"
            if dry_run:
                status = "[yellow]would apply[/yellow]"
            elif result.success:
                status = "[green]applied[/green]"
            else:
                status = "[red]failed[/red]"

        table.add_row(f"[bold]{result.namespace}[/bold]", changes, status)

    console.print(table)


def apply_schema_to_single_namespace(
    namespace: str,
    new_schema: dict[str, object],
    region: str | None,
    dry_run: bool,
    yes: bool,
) -> None:
    """Apply schema to a single namespace with interactive diff display.

    Args:
        namespace: Target namespace name
        new_schema: Schema to apply
        region: Optional region override
        dry_run: If True, only show diff without applying
        yes: If True, skip confirmation prompt
    """
    # Get current schema from namespace
    ns = get_namespace(namespace, region)
    current_schema = get_current_schema(ns)

    # Compute diff
    diff = compute_schema_diff(current_schema, new_schema)

    # Display diff
    display_schema_diff(diff, namespace)

    # Check for conflicts
    if diff.has_conflicts:
        console.print("[red]Error: Cannot apply schema with type conflicts.[/red]")
        console.print("[red]Changing an existing attribute's type is not allowed.[/red]")
        sys.exit(1)

    # Check if there are any changes
    if not diff.has_changes:
        console.print("[green]Schema is already up to date, no changes needed.[/green]")
        return

    # Dry run stops here
    if dry_run:
        console.print("[dim]Dry run mode - no changes applied[/dim]")
        return

    # Confirm unless --yes
    if not yes:
        confirm = click.confirm("Apply these schema changes?", default=False)
        if not confirm:
            console.print("[yellow]Aborted[/yellow]")
            return

    # Apply the schema
    try:
        console.print(f"[dim]Applying schema to {namespace}...[/dim]")
        ns.write(
            upsert_rows=[{"id": "__schema_placeholder__"}],
            schema=new_schema,
        )
        console.print(f"[green]Successfully applied schema to {namespace}[/green]")
    except Exception as e:
        console.print(f"[red]Error applying schema: {e}[/red]")
        sys.exit(1)


def apply_schema_to_multiple_namespaces(
    namespaces: list[str],
    new_schema: dict[str, object],
    region: str | None,
    dry_run: bool,
    yes: bool,
) -> None:
    """Apply schema to multiple namespaces with batch summary display.

    Args:
        namespaces: List of target namespace names
        new_schema: Schema to apply
        region: Optional region override
        dry_run: If True, only show what would change
        yes: If True, skip confirmation prompt
    """
    # Phase 1: Compute diffs for all namespaces
    results: list[BatchApplyResult] = []
    has_any_conflicts = False
    has_any_changes = False

    console.print(f"\n[bold]Analyzing schema for {len(namespaces)} namespace(s)...[/bold]\n")

    for ns_name in namespaces:
        try:
            ns = get_namespace(ns_name, region)
            current_schema = get_current_schema(ns)
            diff = compute_schema_diff(current_schema, new_schema)

            result = BatchApplyResult(
                namespace=ns_name,
                success=False,  # Will be updated after apply
                additions=len(diff.additions),
                conflicts=len(diff.conflicts),
            )

            if diff.has_conflicts:
                has_any_conflicts = True
            if diff.has_changes:
                has_any_changes = True

            results.append(result)
        except Exception as e:
            results.append(BatchApplyResult(
                namespace=ns_name,
                success=False,
                error=str(e),
            ))

    # Display summary table
    console.print(f"[bold]Schema changes for {len(namespaces)} namespace(s):[/bold]\n")
    display_batch_summary(results, dry_run=True)

    # Check for conflicts
    if has_any_conflicts:
        console.print("\n[red]Error: Some namespaces have type conflicts.[/red]")
        console.print("[red]Changing an existing attribute's type is not allowed.[/red]")
        console.print("[dim]Fix conflicts before applying schema changes.[/dim]")
        sys.exit(1)

    # Check if there are any changes
    if not has_any_changes:
        console.print("\n[green]All namespaces are already up to date, no changes needed.[/green]")
        return

    # Dry run stops here
    if dry_run:
        console.print("\n[dim]Dry run mode - no changes applied[/dim]")
        return

    # Count how many namespaces will be updated
    to_update = [r for r in results if r.additions > 0 and r.conflicts == 0 and r.error is None]

    if not to_update:
        console.print("\n[green]No namespaces need updates.[/green]")
        return

    # Confirm unless --yes
    if not yes:
        confirm = click.confirm(f"\nApply schema to {len(to_update)} namespace(s)?", default=False)
        if not confirm:
            console.print("[yellow]Aborted[/yellow]")
            return

    # Phase 2: Apply schema to each namespace
    console.print(f"\n[dim]Applying schema to {len(to_update)} namespace(s)...[/dim]\n")

    success_count = 0
    fail_count = 0

    for result in results:
        if result.additions == 0 or result.conflicts > 0 or result.error is not None:
            continue

        try:
            ns = get_namespace(result.namespace, region)
            ns.write(
                upsert_rows=[{"id": "__schema_placeholder__"}],
                schema=new_schema,
            )
            result.success = True
            success_count += 1
        except Exception as e:
            result.success = False
            result.error = str(e)
            fail_count += 1

    # Display final results
    console.print("[bold]Results:[/bold]\n")
    display_batch_summary(results, dry_run=False)

    # Summary message
    if fail_count == 0:
        console.print(f"\n[green]Successfully applied schema to {success_count} namespace(s)[/green]")
    else:
        console.print(f"\n[yellow]Applied schema to {success_count} namespace(s), {fail_count} failed[/yellow]")
        sys.exit(1)


@schema.command("apply", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--namespace", help="Target namespace to apply schema to")
@click.option("--prefix", help="Apply to all namespaces matching this prefix")
@click.option("--all", "apply_all", is_flag=True, help="Apply to all namespaces")
@click.option("-f", "--file", "schema_file", required=True, help="JSON file containing schema definition")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.option("--dry-run", is_flag=True, help="Show diff only, don't apply changes")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def schema_apply(
    ctx: click.Context,
    namespace: str | None,
    prefix: str | None,
    apply_all: bool,
    schema_file: str,
    region: str | None,
    dry_run: bool,
    yes: bool,
) -> None:
    """Apply a schema from a JSON file to namespace(s).

    Shows a diff of schema changes before applying. Type changes to existing
    attributes are not allowed and will be flagged as conflicts.

    Use -n/--namespace for a single namespace, --prefix to apply to all
    namespaces matching a prefix, or --all to apply to all namespaces.
    """
    # Validate options: must have exactly one of namespace, prefix, or all
    mode_count = sum([bool(namespace), bool(prefix), apply_all])

    if mode_count > 1:
        console.print("[red]Error: Cannot use more than one of --namespace, --prefix, and --all[/red]")
        console.print("[dim]Use -n/--namespace for a single namespace, --prefix for prefix match, or --all for all namespaces[/dim]")
        sys.exit(1)

    if mode_count == 0:
        console.print("[red]Error: Must specify one of --namespace, --prefix, or --all[/red]")
        console.print("[dim]Use -n/--namespace for a single namespace, --prefix for prefix match, or --all for all namespaces[/dim]")
        sys.exit(1)

    # Load schema from file
    new_schema = load_schema_file(schema_file)

    if not new_schema:
        console.print("[yellow]Schema file is empty, nothing to apply[/yellow]")
        return

    if namespace:
        # Single namespace mode
        apply_schema_to_single_namespace(namespace, new_schema, region, dry_run, yes)
    elif prefix:
        # Prefix mode - batch apply
        namespaces = list_namespaces_by_prefix(prefix, region)

        if not namespaces:
            console.print(f"[yellow]No namespaces found matching prefix: {prefix}[/yellow]")
            return

        console.print(f"[dim]Found {len(namespaces)} namespace(s) matching prefix '{prefix}'[/dim]")
        apply_schema_to_multiple_namespaces(namespaces, new_schema, region, dry_run, yes)
    else:
        # All namespaces mode
        namespaces = list_all_namespaces(region)

        if not namespaces:
            console.print("[yellow]No namespaces found[/yellow]")
            return

        console.print(f"[dim]Found {len(namespaces)} namespace(s)[/dim]")
        apply_schema_to_multiple_namespaces(namespaces, new_schema, region, dry_run, yes)


def get_namespace_row_count(ns) -> int | None:
    """Get the row count for a namespace.

    Args:
        ns: The turbopuffer namespace object

    Returns:
        The number of rows, or None if namespace doesn't exist
    """
    try:
        metadata = ns.metadata()
        return metadata.approx_count if hasattr(metadata, "approx_count") else 0
    except Exception:
        return None


def display_schema_for_copy(schema_dict: dict[str, object], source: str, target: str) -> None:
    """Display the schema that will be copied.

    Args:
        schema_dict: The schema dictionary
        source: Source namespace name
        target: Target namespace name
    """
    console.print(f"\n[bold]Copying schema from:[/bold] {source}")
    console.print(f"[bold]Creating namespace: [/bold] {target}")
    console.print("\n[bold]Schema:[/bold]")

    if not schema_dict:
        console.print("[dim]  (no schema attributes)[/dim]")
    else:
        for attr, attr_type in sorted(schema_dict.items()):
            type_display = schema_type_for_display(attr_type)
            console.print(f"  {attr}: {type_display}")

    console.print("\n[dim]Note: A placeholder row will be created to initialize the namespace.[/dim]\n")


@schema.command("copy", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--namespace", required=True, help="Source namespace to copy schema from")
@click.option("--to", "target", required=True, help="Target namespace name (must not exist or be empty)")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def schema_copy(
    ctx: click.Context,
    namespace: str,
    target: str,
    region: str | None,
    yes: bool,
) -> None:
    """Copy schema from a source namespace to a new target namespace.

    The target namespace must be empty or non-existent. A placeholder row
    will be created to initialize the namespace with the schema.
    """
    # Get source namespace and schema
    source_ns = get_namespace(namespace, region)
    source_schema = get_current_schema(source_ns)

    if source_schema is None:
        console.print(f"[red]Error: Source namespace '{namespace}' has no schema or does not exist[/red]")
        sys.exit(1)

    # Check target namespace
    target_ns = get_namespace(target, region)
    target_row_count = get_namespace_row_count(target_ns)

    if target_row_count is not None and target_row_count > 0:
        console.print(f"[red]Error: Target namespace '{target}' already has {target_row_count} row(s)[/red]")
        console.print("[red]Target namespace must be empty or non-existent[/red]")
        sys.exit(1)

    # Display what will be copied
    display_schema_for_copy(source_schema, namespace, target)

    # Confirm unless --yes
    if not yes:
        confirm = click.confirm("Copy schema to target namespace?", default=False)
        if not confirm:
            console.print("[yellow]Aborted[/yellow]")
            return

    # Create target namespace with schema
    try:
        console.print(f"[dim]Creating namespace {target} with schema...[/dim]")
        target_ns.write(
            upsert_rows=[{"id": "__schema_placeholder__"}],
            schema=source_schema,
        )
        console.print(f"[green]Successfully created namespace '{target}' with schema from '{namespace}'[/green]")
    except Exception as e:
        console.print(f"[red]Error creating namespace: {e}[/red]")
        sys.exit(1)

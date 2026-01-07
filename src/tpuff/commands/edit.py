"""Edit command for tpuff CLI."""

import json
import os
import subprocess
import sys
import tempfile

import click
from rich.console import Console

from tpuff.client import get_namespace
from tpuff.utils.debug import debug_log


console = Console()


@click.command("edit")
@click.argument("id")
@click.option("-n", "--namespace", required=True, help="Namespace to query")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.pass_context
def edit(
    ctx: click.Context,
    id: str,
    namespace: str,
    region: str | None,
) -> None:
    """Edit a document by ID from a namespace using vim."""
    try:
        console.print(f"\n[bold]Fetching document with ID: {id} from namespace: {namespace}[/bold]\n")

        # Get namespace reference
        ns = get_namespace(namespace, region)

        query_params = {
            "filters": ["id", "Eq", id],
            "top_k": 1,
            "include_attributes": True,
        }

        # Debug: Log query parameters
        debug_log("Query Parameters", query_params)

        # Query with id filter
        result = ns.query(**query_params)

        # Debug: Log API response
        debug_log("Query Response", result)

        # Extract rows from the response
        rows = result.rows if hasattr(result, "rows") else []

        # Check if document was found
        if not rows:
            console.print("[yellow]Document not found[/yellow]")
            sys.exit(1)

        # Get the document and remove the vector field
        doc = rows[0]

        # Convert to dict
        if hasattr(doc, "model_dump"):
            doc_dict = doc.model_dump()
        elif hasattr(doc, "to_dict"):
            doc_dict = doc.to_dict()
        else:
            doc_dict = {"id": getattr(doc, "id", "N/A")}

        # Save the original vector
        original_vector = doc_dict.get("vector")

        # Create document for editing (without vector)
        doc_without_vector = {k: v for k, v in doc_dict.items() if k != "vector"}

        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp_file:
            original_content = json.dumps(doc_without_vector, indent=2, default=str)
            tmp_file.write(original_content)
            tmp_file_path = tmp_file.name

        console.print("[cyan]Opening vim editor...[/cyan]")
        console.print(
            "[dim]Save and quit (:wq) to upsert changes, or quit without saving (:q!) to cancel.[/dim]\n"
        )

        # Open vim
        try:
            result_code = subprocess.call(["vim", tmp_file_path])
            if result_code != 0:
                console.print(f"[red]vim exited with code {result_code}[/red]")
                sys.exit(1)
        except FileNotFoundError:
            console.print("[red]Error: vim not found. Please install vim or ensure it's in your PATH.[/red]")
            sys.exit(1)

        # Read the edited content
        with open(tmp_file_path, "r") as f:
            edited_content = f.read()

        # Clean up temp file
        os.unlink(tmp_file_path)

        # Check if content was actually changed
        if edited_content == original_content:
            console.print("\n[yellow]No changes made. Skipping upsert.[/yellow]")
            sys.exit(0)

        # Parse the edited JSON
        try:
            edited_doc = json.loads(edited_content)
        except json.JSONDecodeError as e:
            console.print(f"\n[red]Error: Invalid JSON format: {e}[/red]")
            sys.exit(1)

        # Restore the vector and ensure id is preserved
        if original_vector is not None:
            edited_doc["vector"] = original_vector
        edited_doc["id"] = id

        # Upsert the document
        console.print("\n[cyan]Upserting document...[/cyan]")

        upsert_params = {"upsert_rows": [edited_doc]}

        debug_log("Upsert Parameters", upsert_params)
        ns.upsert(**upsert_params)
        debug_log("Upsert Response", "Success")

        console.print("[green]✓ Document updated successfully[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

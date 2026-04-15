"""Scan command for tpuff CLI — extract unique field values from a namespace."""

import json
import sys

import click
from rich.console import Console

from tpuff.client import get_namespace
from tpuff.utils.debug import debug_log
from tpuff.utils.output import is_plain

# stderr console so progress doesn't pollute JSON output
err_console = Console(stderr=True)


@click.command("scan", context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--namespace", required=True, help="Namespace to scan")
@click.option("--field", required=True, help="Field name to extract unique values from")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.option("--page-size", default=1000, type=int, help="Batch size per query (default: 1000)")
@click.pass_context
def scan(
    ctx: click.Context,
    namespace: str,
    field: str,
    region: str | None,
    page_size: int,
) -> None:
    """Scan a namespace and extract all unique values of a field."""
    plain = is_plain(ctx)

    try:
        ns = get_namespace(namespace, region)

        # Get total document count from metadata for progress bar
        metadata = ns.metadata()
        meta_dict = metadata.model_dump() if hasattr(metadata, "model_dump") else {}
        total_docs = meta_dict.get("approx_row_count") or None

        unique_values: set[str] = set()
        last_id: str | None = None
        total_scanned = 0

        if not plain:
            from rich.progress import (
                BarColumn,
                MofNCompleteColumn,
                Progress,
                SpinnerColumn,
                TextColumn,
            )

            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=None),
                MofNCompleteColumn(),
                console=err_console,
            )
            task = progress.add_task("Scanning...", total=total_docs)
            progress.start()

        while True:
            query_params: dict = {
                "rank_by": ["id", "asc"],
                "include_attributes": [field],
                "top_k": page_size,
            }

            if last_id is not None:
                query_params["filters"] = ["id", "Gt", last_id]

            debug_log("Scan query", query_params)
            result = ns.query(**query_params)
            rows = result.rows if hasattr(result, "rows") else []

            for row in rows:
                if hasattr(row, "model_dump"):
                    row_dict = row.model_dump()
                else:
                    row_dict = {"id": getattr(row, "id", None)}

                value = row_dict.get(field)
                if value is not None:
                    unique_values.add(value)

                last_id = row_dict.get("id", getattr(row, "id", None))

            total_scanned += len(rows)

            if not plain:
                progress.update(
                    task,
                    completed=total_scanned,
                    description=f"{len(unique_values)} unique values",
                )

            debug_log("Scan page", {
                "rows": len(rows),
                "total_scanned": total_scanned,
                "unique_values": len(unique_values),
                "last_id": last_id,
            })

            if len(rows) < page_size:
                break

        if not plain:
            progress.stop()
            err_console.print(
                f"[green]Done.[/green] Scanned {total_scanned} documents, "
                f"found {len(unique_values)} unique values."
            )

        # Output the unique values as a sorted JSON array to stdout
        click.echo(json.dumps(sorted(unique_values)))

    except Exception as e:
        if not plain:
            try:
                progress.stop()
            except Exception:
                pass
        err_console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

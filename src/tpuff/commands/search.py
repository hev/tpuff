"""Search command for tpuff CLI."""

import json
import re
import sys
import time

import click
from rich.console import Console
from rich.table import Table

from tpuff.client import get_namespace
from tpuff.utils.debug import debug_log
from tpuff.utils.embeddings import embedding_generator
from tpuff.utils.output import is_plain, print_table_plain, status_print

console = Console()


def extract_vector_info(schema: dict) -> dict | None:
    """Extract vector attribute name and dimensions from namespace schema.

    Args:
        schema: The namespace schema.

    Returns:
        Dict with attributeName and dimensions, or None if no vector found.
    """
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


@click.command("search", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("query")
@click.option("-n", "--namespace", required=True, help="Namespace to search in")
@click.option(
    "-m", "--model", "model_id", help="HuggingFace model ID for vector search (e.g., sentence-transformers/all-MiniLM-L6-v2)"
)
@click.option("-k", "--top-k", default=10, type=int, help="Number of results to return")
@click.option(
    "-d",
    "--distance-metric",
    type=click.Choice(["cosine_distance", "euclidean_squared"]),
    default="cosine_distance",
    help="Distance metric for vector search",
)
@click.option("-f", "--filters", help="Additional filters in JSON format")
@click.option("--fts", "fts_field", help="Field name to use for full-text search (BM25)")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    namespace: str,
    model_id: str | None,
    top_k: int,
    distance_metric: str,
    filters: str | None,
    fts_field: str | None,
    region: str | None,
) -> None:
    """Search for documents in a namespace using vector similarity or full-text search."""
    plain = is_plain(ctx)
    use_fts = bool(fts_field)

    # Validate options
    if not use_fts and not model_id:
        console.print("[red]Error: Either --model or --fts must be specified[/red]")
        console.print("[yellow]  Use --model for vector similarity search[/yellow]")
        console.print("[yellow]  Use --fts for full-text search[/yellow]")
        sys.exit(1)

    if use_fts and model_id:
        status_print(ctx, "[yellow]Warning: Both --fts and --model specified. Using FTS mode.[/yellow]", console)

    status_print(ctx, f"\n[bold]Searching in namespace: {namespace}[/bold]", console)
    status_print(ctx, f'[dim]Query: "{query}"[/dim]', console)

    try:
        ns = get_namespace(namespace, region)

        # Get namespace metadata to find vector attribute name (for exclude_attributes)
        metadata = ns.metadata()
        schema_dict = metadata.model_dump().get("schema", {})
        vector_info = extract_vector_info(schema_dict)

        if use_fts:
            # Full-text search mode
            status_print(ctx, f'[dim]Mode: Full-text search (BM25) on field "{fts_field}"[/dim]\n', console)

            query_params = {
                "rank_by": [fts_field, "BM25", query],
                "top_k": top_k,
            }
            if vector_info:
                query_params["exclude_attributes"] = [vector_info["attributeName"]]
        else:
            # Vector search mode
            status_print(ctx, "[dim]Mode: Vector similarity search[/dim]", console)
            status_print(ctx, f"[dim]Model: {model_id}[/dim]\n", console)

            # Generate embedding for query
            try:
                embedding = embedding_generator.generate_embedding(query, model_id)
            except Exception as e:
                error_msg = str(e)

                # Check if it's a model loading error
                if "Could not locate" in error_msg or "not found" in error_msg.lower():
                    console.print("\n[red]Error: Failed to load model[/red]")
                    console.print("\n[dim]Popular embedding models:[/dim]")
                    console.print("[dim]  • sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)[/dim]")
                    console.print("[dim]  • sentence-transformers/all-mpnet-base-v2 (768 dimensions)[/dim]")
                    console.print("[dim]  • BAAI/bge-small-en-v1.5 (384 dimensions)[/dim]")
                    console.print("[dim]  • BAAI/bge-base-en-v1.5 (768 dimensions)[/dim]")
                    console.print(
                        "\n[dim]Browse models: https://huggingface.co/models?library=sentence-transformers[/dim]\n"
                    )
                    sys.exit(1)

                # Re-raise other errors
                raise

            status_print(ctx, f"[dim]Generated {len(embedding)}-dimensional embedding[/dim]\n", console)

            # Verify vector configuration
            if not vector_info:
                console.print("[red]Error: No vector attribute found in namespace schema[/red]")
                sys.exit(1)

            # Verify dimensions match
            if vector_info["dimensions"] != len(embedding):
                console.print("[red]Error: Dimension mismatch![/red]")
                console.print(
                    f"[yellow]  Expected: {vector_info['dimensions']} dimensions (from namespace schema)[/yellow]"
                )
                console.print(f"[yellow]  Got: {len(embedding)} dimensions (from model {model_id})[/yellow]")
                console.print(
                    "[yellow]\nThe namespace may have been created with a different embedding model.[/yellow]"
                )
                sys.exit(1)

            status_print(ctx, f"[dim]Using distance metric: {distance_metric}[/dim]\n", console)

            query_params = {
                "rank_by": [vector_info["attributeName"], "ANN", embedding],
                "top_k": top_k,
                "distance_metric": distance_metric,
                "exclude_attributes": [vector_info["attributeName"]],
            }

        # Parse filters if provided
        parsed_filters = None
        if filters:
            try:
                parsed_filters = json.loads(filters)
            except json.JSONDecodeError:
                console.print("[red]Error: Invalid filter JSON format[/red]")
                console.print("""[yellow]Example: -f '["category", "In", ["tech", "science"]]'[/yellow]""")
                sys.exit(1)

        if parsed_filters:
            query_params["filters"] = parsed_filters

        # Debug: Log query parameters
        debug_log("Query Parameters", query_params)

        # Query the namespace
        start_time = time.time()
        result = ns.query(**query_params)
        query_time = (time.time() - start_time) * 1000  # Convert to ms

        # Debug: Log API response
        debug_log("Query Response", result)

        # Extract rows from the response
        rows = result.rows if hasattr(result, "rows") else []

        if not rows:
            console.print("[yellow]No documents found matching the query[/yellow]")
            return

        # Debug: Log first row structure
        if rows:
            first_row = rows[0]
            if hasattr(first_row, "model_dump"):
                debug_log("First Row Structure", {"keys": list(first_row.model_dump().keys())})

        status_print(ctx, f"[bold]Found {len(rows)} result(s):[/bold]\n", console)

        # Collect row data
        score_header = "Score" if use_fts else "Distance"
        table_rows = []
        for row in rows:
            # Get the row as a dict
            if hasattr(row, "model_dump"):
                row_dict = row.model_dump()
            elif hasattr(row, "to_dict"):
                row_dict = row.to_dict()
            else:
                row_dict = {"id": getattr(row, "id", "N/A")}

            row_id = row_dict.get("id", getattr(row, "id", "N/A"))

            if use_fts:
                # Show only the FTS field
                field_value = row_dict.get(fts_field, "N/A")
                display_contents = str(field_value) if field_value is not None else "N/A"
            else:
                # Vector search: show all attributes except system fields
                contents = {}
                exclude_keys = {"id", "vector", "$dist", "dist", "$score", "attributes"}
                for key, value in row_dict.items():
                    if key not in exclude_keys and not key.startswith("_"):
                        contents[key] = value

                display_contents = json.dumps(contents, default=str)

            # Get distance/score value
            dist_value = row_dict.get("$dist") or row_dict.get("dist")
            if plain:
                score_display = f"{dist_value:.4f}" if dist_value is not None else "N/A"
            else:
                score_display = f"{dist_value:.4f}" if dist_value is not None else "[dim]N/A[/dim]"

            table_rows.append([str(row_id), display_contents, score_display])

        if plain:
            print_table_plain(["ID", "Contents", score_header], table_rows)
        else:
            table = Table(show_header=True, header_style="cyan")
            table.add_column("ID")
            table.add_column("Contents")
            table.add_column(score_header)
            for r in table_rows:
                table.add_row(*r)
            console.print(table)

        # Show performance info
        if hasattr(result, "performance") and result.performance:
            status_print(
                ctx,
                f"\n[dim]Search completed in {query_time:.0f}ms (query execution: {result.performance.query_execution_ms:.2f}ms)[/dim]",
                console,
            )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

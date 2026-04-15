"""Output mode utilities for tpuff CLI.

Supports two output modes:
- human: Rich tables with colors, emojis, decorative messages (default in TTY)
- plain: Pipe-delimited, data-only rows for agent/script consumption (default when piped)
"""

import sys

import click


def resolve_output_mode(explicit: str | None) -> str:
    """Resolve the output mode from explicit flag or TTY auto-detection.

    Args:
        explicit: The user-specified mode ("human" or "plain"), or None for auto.

    Returns:
        "human" or "plain"
    """
    if explicit:
        return explicit
    return "human" if sys.stdout.isatty() else "plain"


def is_plain(ctx: click.Context) -> bool:
    """Check if the current output mode is plain.

    Args:
        ctx: Click context with output_mode in obj dict.

    Returns:
        True if output mode is "plain".
    """
    return (ctx.obj or {}).get("output_mode") == "plain"


def print_table_plain(headers: list[str], rows: list[list[str]]) -> None:
    """Print a pipe-delimited table to stdout.

    Args:
        headers: Column header names.
        rows: List of row data (each row is a list of strings).
    """
    click.echo("|".join(headers))
    for row in rows:
        click.echo("|".join(str(v) for v in row))


def status_print(ctx: click.Context, message: str, console) -> None:
    """Print a decorative/status message only in human mode.

    Args:
        ctx: Click context with output_mode in obj dict.
        message: Rich-formatted message string.
        console: Rich Console instance.
    """
    if not is_plain(ctx):
        console.print(message)

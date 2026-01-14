"""Main CLI entry point for tpuff."""

import click

from tpuff import __version__
from tpuff.commands.list import list_cmd
from tpuff.commands.search import search
from tpuff.commands.delete import delete
from tpuff.commands.edit import edit
from tpuff.commands.get import get
from tpuff.commands.export import export
from tpuff.commands.schema import schema


# Context settings to enable -h as help alias for all commands
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="tpuff")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """tpuff - CLI tool for Turbopuffer vector database."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug


# Register commands
cli.add_command(list_cmd, name="list")
cli.add_command(list_cmd, name="ls")  # alias
cli.add_command(search)
cli.add_command(delete)
cli.add_command(delete, name="rm")  # alias
cli.add_command(edit)
cli.add_command(get)
cli.add_command(export)
cli.add_command(export, name="metrics")  # alias
cli.add_command(schema)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()

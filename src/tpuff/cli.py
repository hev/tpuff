"""Main CLI entry point for tpuff."""

import click

from tpuff import __version__
from tpuff.commands.delete import delete
from tpuff.commands.edit import edit
from tpuff.commands.env import env
from tpuff.commands.export import export
from tpuff.commands.get import get
from tpuff.commands.list import list_cmd
from tpuff.commands.scan import scan
from tpuff.commands.schema import schema
from tpuff.commands.search import search
from tpuff.utils.output import resolve_output_mode

# Context settings to enable -h as help alias for all commands
CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="tpuff")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option(
    "-o",
    "--output",
    type=click.Choice(["human", "plain"]),
    default=None,
    help="Output format: human (rich tables) or plain (pipe-delimited). Auto-detects TTY if omitted.",
)
@click.option(
    "--env",
    "env_name",
    default=None,
    help="Use a specific named environment from ~/.tpuff/config.toml.",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool, output: str | None, env_name: str | None) -> None:
    """tpuff - CLI tool for Turbopuffer vector database."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug
    ctx.obj["output_mode"] = resolve_output_mode(output)
    ctx.obj["env"] = env_name


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
cli.add_command(scan)
cli.add_command(schema)
cli.add_command(env)


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()

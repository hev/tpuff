"""Environment management commands for tpuff."""

import click
from rich.console import Console
from rich.table import Table

from tpuff.config import add_env, get_active_env, list_envs, remove_env, set_active
from tpuff.utils.output import is_plain, print_table_plain
from tpuff.utils.regions import DEFAULT_REGION, TURBOPUFFER_REGIONS

console = Console()


def mask_key(api_key: str) -> str:
    """Mask an API key, showing only the first 8 characters."""
    if len(api_key) <= 8:
        return api_key
    return api_key[:8] + "..."


@click.group("env", context_settings={"help_option_names": ["-h", "--help"]})
def env():
    """Manage tpuff environments."""
    pass


@env.command("add")
@click.argument("name")
@click.pass_context
def env_add(ctx: click.Context, name: str) -> None:
    """Add a new environment (interactive setup)."""
    api_key = click.prompt("API key", hide_input=True)
    region = click.prompt(
        "Region",
        type=click.Choice(TURBOPUFFER_REGIONS, case_sensitive=False),
        default=DEFAULT_REGION,
    )
    base_url = click.prompt("Base URL (optional, press Enter to skip)", default="")

    add_env(name, api_key, region, base_url)
    click.echo(f"Environment '{name}' added.")

    # Show if it was set as active
    active = get_active_env()
    if active and active[0] == name:
        click.echo("Set as active environment.")


@env.command("use")
@click.argument("name")
def env_use(name: str) -> None:
    """Switch active environment."""
    set_active(name)
    click.echo(f"Switched to environment '{name}'.")


@env.command("list")
@click.pass_context
def env_list(ctx: click.Context) -> None:
    """List all environments."""
    envs = list_envs()
    if not envs:
        click.echo("No environments configured. Run 'tpuff env add <name>' to add one.")
        return

    plain = is_plain(ctx)
    headers = ["", "Name", "Region", "API Key"]
    rows = []
    for name, env_dict, is_active in envs:
        marker = "*" if is_active else ""
        rows.append([
            marker,
            name,
            env_dict.get("region", DEFAULT_REGION),
            mask_key(env_dict.get("api_key", "")),
        ])

    if plain:
        print_table_plain(headers, rows)
    else:
        table = Table(show_header=True, header_style="cyan")
        for h in headers:
            table.add_column(h)
        for r in rows:
            # Highlight active env
            if r[0] == "*":
                table.add_row(
                    "[green]*[/green]",
                    f"[bold]{r[1]}[/bold]",
                    r[2],
                    f"[dim]{r[3]}[/dim]",
                )
            else:
                table.add_row("", r[1], r[2], f"[dim]{r[3]}[/dim]")
        console.print(table)


# Alias
env.add_command(env_list, name="ls")


@env.command("rm")
@click.argument("name")
@click.confirmation_option(prompt="Are you sure you want to remove this environment?")
def env_rm(name: str) -> None:
    """Remove an environment."""
    remove_env(name)
    click.echo(f"Environment '{name}' removed.")


@env.command("show")
def env_show() -> None:
    """Show the current active environment."""
    active = get_active_env()
    if not active:
        click.echo("No active environment. Run 'tpuff env add <name>' to add one.")
        return

    name, env_dict = active
    click.echo(f"Active environment: {name}")
    click.echo(f"  Region:   {env_dict.get('region', DEFAULT_REGION)}")
    click.echo(f"  API Key:  {mask_key(env_dict.get('api_key', ''))}")
    base_url = env_dict.get("base_url", "")
    if base_url:
        click.echo(f"  Base URL: {base_url}")

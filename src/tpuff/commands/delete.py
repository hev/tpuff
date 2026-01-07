"""Delete command for tpuff CLI."""

import sys

import click
from rich.console import Console

from tpuff.client import get_turbopuffer_client
from tpuff.utils.debug import debug_log


console = Console()


def prompt_user(message: str) -> str:
    """Prompt the user for input."""
    return click.prompt(message, default="", show_default=False).strip()


@click.command("delete")
@click.option("-n", "--namespace", help="Namespace to delete")
@click.option("--all", "delete_all", is_flag=True, help="Delete all namespaces")
@click.option("--prefix", help="Delete all namespaces starting with prefix")
@click.option("-r", "--region", help="Override the region (e.g., aws-us-east-1, gcp-us-central1)")
@click.pass_context
def delete(
    ctx: click.Context,
    namespace: str | None,
    delete_all: bool,
    prefix: str | None,
    region: str | None,
) -> None:
    """Delete namespace(s)."""
    client = get_turbopuffer_client(region)

    try:
        # Validate that exactly one option is provided
        options_count = sum([bool(namespace), delete_all, bool(prefix)])

        if options_count == 0:
            console.print("[red]Error: You must specify either -n <namespace>, --all, or --prefix <prefix>[/red]")
            console.print("\nUsage:")
            console.print("  tpuff delete -n <namespace>       Delete a specific namespace")
            console.print("  tpuff delete --all                Delete all namespaces")
            console.print("  tpuff delete --prefix <prefix>    Delete all namespaces starting with prefix")
            sys.exit(1)

        if options_count > 1:
            console.print("[red]Error: Cannot use multiple deletion options together[/red]")
            console.print("[dim]Please use only one of: -n, --all, or --prefix[/dim]")
            sys.exit(1)

        if namespace:
            # Delete single namespace
            console.print(f"\n[yellow]⚠️  You are about to delete namespace: [bold]{namespace}[/bold][/yellow]")
            console.print("[dim]This action cannot be undone.[/dim]\n")

            answer = prompt_user("Are you sure? (y/n)")

            if answer.lower() not in ("y", "yes"):
                console.print("[dim]Deletion cancelled.[/dim]")
                sys.exit(0)

            # Delete the namespace
            console.print(f"\n[dim]Deleting namespace {namespace}...[/dim]")
            ns = client.namespace(namespace)

            debug_log("Delete Parameters", {"namespace": namespace})
            ns.delete_all()
            debug_log("Delete Response", "Success")

            console.print(f"[green]✓ Namespace [bold]{namespace}[/bold] deleted successfully![/green]")

        elif delete_all:
            # Delete all namespaces
            console.print("[bold yellow]\n🚨 DANGER ZONE 🚨[/bold yellow]")
            console.print("[red]You are about to delete ALL namespaces![/red]")
            console.print("[dim]This will permanently destroy all your data.[/dim]\n")

            # First, list all namespaces
            namespaces_iter = client.namespaces()
            debug_log("Namespaces API Response", namespaces_iter)
            namespaces = list(namespaces_iter)

            if not namespaces:
                console.print("[dim]No namespaces found. Nothing to delete.[/dim]")
                sys.exit(0)

            console.print(f"[yellow]Found {len(namespaces)} namespace(s):[/yellow]")
            for ns in namespaces:
                console.print(f"[dim]  - {ns.id}[/dim]")

            console.print("\n[bold yellow]💀 This is your last chance to back out! 💀[/bold yellow]")
            console.print(f"[dim]To confirm, please type: [bold red]yolo[/bold red][/dim]\n")

            answer = prompt_user(">")

            if answer != "yolo":
                console.print("\n[green]✨ Wise choice! Your data lives to see another day.[/green]")
                console.print("[dim](Phew, that was close!)[/dim]")
                sys.exit(0)

            # User typed yolo, proceed with deletion
            console.print("\n[bold red]🎢 YOLO MODE ACTIVATED! 🎢[/bold red]")
            console.print("[dim]Deleting all namespaces...[/dim]\n")

            success_count = 0
            fail_count = 0

            for ns in namespaces:
                try:
                    debug_log("Deleting namespace", {"namespace": ns.id})
                    client.namespace(ns.id).delete_all()
                    debug_log("Delete Response", "Success")
                    console.print(f"[dim]  ✓ Deleted: {ns.id}[/dim]")
                    success_count += 1
                except Exception as e:
                    debug_log("Delete Error", str(e))
                    console.print(f"[red]  ✗ Failed to delete: {ns.id}[/red]")
                    console.print(f"[dim]    Error: {e}[/dim]")
                    fail_count += 1

            console.print("\n[bold green]🎉 Deletion complete![/bold green]")
            console.print(f"[dim]Successfully deleted: {success_count}[/dim]")
            if fail_count > 0:
                console.print(f"[red]Failed: {fail_count}[/red]")
            console.print("[dim]\n(Hope you had backups! 😅)[/dim]")

        elif prefix:
            # Delete namespaces by prefix
            console.print(f"\n[yellow]🔍 Searching for namespaces with prefix: [bold]{prefix}[/bold][/yellow]")
            console.print("[dim](Using case-insensitive matching)[/dim]\n")

            # Fetch all namespaces
            namespaces_iter = client.namespaces()
            debug_log("Namespaces API Response", namespaces_iter)
            all_namespaces = list(namespaces_iter)

            # Filter by prefix (case-insensitive)
            matching_namespaces = [
                ns for ns in all_namespaces if ns.id.lower().startswith(prefix.lower())
            ]

            if not matching_namespaces:
                console.print(f'[dim]No namespaces found with prefix "{prefix}".[/dim]')
                console.print("[dim]Nothing to delete.[/dim]")
                sys.exit(0)

            console.print(f'[yellow]Found {len(matching_namespaces)} namespace(s) matching prefix "{prefix}":[/yellow]')
            for ns in matching_namespaces:
                console.print(f"[dim]  - {ns.id}[/dim]")

            console.print("\n[bold yellow]⚠️  WARNING: This will permanently delete these namespaces![/bold yellow]")
            console.print(f"[dim]To confirm, please type the prefix: [bold red]{prefix}[/bold red][/dim]\n")

            answer = prompt_user(">")

            if answer.lower() != prefix.lower():
                console.print("\n[green]✨ Deletion cancelled.[/green]")
                console.print("[dim]Your data is safe![/dim]")
                sys.exit(0)

            # User confirmed, proceed with deletion
            console.print("\n[bold red]🗑️  Starting deletion...[/bold red]")
            console.print("")

            success_count = 0
            fail_count = 0

            for ns in matching_namespaces:
                try:
                    debug_log("Deleting namespace", {"namespace": ns.id})
                    client.namespace(ns.id).delete_all()
                    debug_log("Delete Response", "Success")
                    console.print(f"[dim]  ✓ Deleted: {ns.id}[/dim]")
                    success_count += 1
                except Exception as e:
                    debug_log("Delete Error", str(e))
                    console.print(f"[red]  ✗ Failed to delete: {ns.id}[/red]")
                    console.print(f"[dim]    Error: {e}[/dim]")
                    fail_count += 1

            console.print("\n[bold green]✓ Deletion complete![/bold green]")
            console.print(f"[dim]Successfully deleted: {success_count}[/dim]")
            if fail_count > 0:
                console.print(f"[red]Failed: {fail_count}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

# constitution_cli.py
"""
CLI interface for the Constitution Manager, built with Typer.
This separates the CLI concerns from the core functionality.
"""
import os
import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
import datetime # Ensure datetime is imported

from constitution_manager import constitution_manager, DISALLOWED_ID_CHARS
from utils import shout_if_fails

# Create Typer app for constitution management
app = typer.Typer(help="Manage constitutions for the Superego system")
console = Console()

def get_editor() -> str:
    """Get the configured editor."""
    return os.environ.get("EDITOR", "nano")

@shout_if_fails
@app.command("list", help="List all available constitutions.")
def list_constitutions():
    constitutions = constitution_manager.get_available_constitutions()

    if not constitutions:
        console.print("[yellow]No constitutions found.[/yellow]")
        return

    table = Table(title="Available Constitutions", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", min_width=15, overflow="fold")
    table.add_column("Title", style="green", overflow="fold")
    table.add_column("Size", justify="right", style="blue")
    table.add_column("Last Modified", style="magenta")

    for const in constitutions:
        id_text = const['id']
        size = f"{const['size'] / 1024:.1f} KB" if const.get('size') else "N/A"
        last_modified_ts = const.get("last_modified")
        last_modified = datetime.datetime.fromtimestamp(last_modified_ts).strftime("%Y-%m-%d %H:%M") if last_modified_ts else "N/A"
        table.add_row(id_text, const.get("title", "N/A"), size, last_modified)

    console.print("\n")
    console.print(table)
    console.print("\nUse [bold cyan]/use ID[+ID2+ID3][/bold cyan] to select constitution(s) for the next prompt.")
    console.print("Use [bold cyan]/compare [ID1+ID2, ID3, ID4+ID5][/bold cyan] to compare constitution sets.\n")


@shout_if_fails
@app.command("view", help="View the content of a specific constitution. Use '+' to view combined content.")
def view_constitution(
    constitution_ids: str = typer.Argument(
        ...,
        help=f"ID or IDs (separated by '+') of the constitution(s) to view. Disallowed chars in ID: '{DISALLOWED_ID_CHARS}'"
    )
):
    ids_to_load = [id.strip() for id in constitution_ids.split('+') if id.strip()]
    if not ids_to_load:
        console.print("[red]No valid constitution IDs provided.[/red]")
        return

    if any(not constitution_manager._is_valid_id(id) for id in ids_to_load):
         invalid_ids = [id for id in ids_to_load if not constitution_manager._is_valid_id(id)]
         console.print(f"[red]Invalid constitution ID(s): {invalid_ids}. Cannot contain: '{DISALLOWED_ID_CHARS}'[/red]")
         return

    combined_content, loaded_ids = constitution_manager.get_combined_constitution_content(ids_to_load)

    if not combined_content:
        console.print(f"[red]Constitution(s) '{'+'.join(ids_to_load)}' not found or empty.[/red]")
        return

    title = '+'.join(loaded_ids)
    console.print(f"\n[cyan]CONSTITUTION(S): {title}[/cyan]")
    # Use Markdown to render potential markdown within constitutions
    console.print(Panel(Markdown(combined_content), title=title, border_style="cyan", expand=False))

    if len(loaded_ids) < len(ids_to_load):
        missing_ids = set(ids_to_load) - set(loaded_ids)
        console.print(f"[yellow]Warning: Could not load constitution(s): {', '.join(missing_ids)}[/yellow]")

@shout_if_fails
@app.command("edit", help="Edit a constitution file.")
def edit_constitution(
    constitution_id: str = typer.Argument(
        ...,
        help=f"ID of the constitution to edit. Disallowed chars: '{DISALLOWED_ID_CHARS}'"
    ),
    editor: Optional[str] = typer.Option(
        None, "--editor", "-e",
        help="Editor to use (defaults to EDITOR env variable or nano)"
    )
):
    if not constitution_manager._is_valid_id(constitution_id):
         console.print(f"[red]Invalid constitution ID '{constitution_id}'. Cannot contain: '{DISALLOWED_ID_CHARS}'[/red]")
         return

    content = constitution_manager.get_constitution_content(constitution_id)
    if content is None: # Check for None explicitly, as "" is valid content
        console.print(f"[red]Constitution '{constitution_id}' not found. Use 'create' first.[/red]")
        return

    editor_to_use = editor or get_editor()
    console.print(f"[cyan]Editing constitution: {constitution_id}[/cyan]")
    console.print(f"[yellow]Opening in {editor_to_use}...[/yellow]")

    # Open in editor, get updated content if changed
    updated_content = constitution_manager.edit_in_temp_file(content, editor=editor_to_use)

    if updated_content is not None:
        if constitution_manager.save_constitution(constitution_id, updated_content):
            console.print(f"[green]Constitution '{constitution_id}' saved successfully.[/green]")
        else:
            # Save_constitution prints its own errors
            pass
    else:
         console.print("[cyan]No changes detected or edit aborted.[/cyan]")


@shout_if_fails
@app.command("create", help="Create a new constitution.")
def create_new_constitution(
    constitution_id: str = typer.Argument(
        ...,
        help=f"ID for the new constitution. Disallowed chars: '{DISALLOWED_ID_CHARS}'"
    ),
    editor: Optional[str] = typer.Option(
        None, "--editor", "-e",
        help="Editor to use (defaults to EDITOR env variable or nano)"
    )
):
    if not constitution_manager._is_valid_id(constitution_id):
         console.print(f"[red]Invalid constitution ID '{constitution_id}'. Cannot contain: '{DISALLOWED_ID_CHARS}'[/red]")
         return

    existing_path = constitution_manager.constitutions_dir / f"{constitution_id}.md"
    if existing_path.exists():
        console.print(f"[yellow]Constitution '{constitution_id}' already exists. Use 'edit' instead.[/yellow]")
        return

    template = f"# {constitution_id.replace('-', ' ').title()}\n\nAdd your constitution rules here."

    editor_to_use = editor or get_editor()
    console.print(f"[cyan]Creating new constitution: {constitution_id}[/cyan]")
    console.print(f"[yellow]Opening template in {editor_to_use}...[/yellow]")

    # Open in editor
    updated_content = constitution_manager.edit_in_temp_file(template, editor=editor_to_use)

    if updated_content is not None and updated_content.strip() != template.strip():
        # Save new content if it was changed from the template
        if constitution_manager.save_constitution(constitution_id, updated_content):
            console.print(f"[green]Constitution '{constitution_id}' created successfully.[/green]")
        else:
            # save_constitution prints its own errors
            pass
    else:
         console.print("[cyan]No content added or edit aborted. Constitution not created.[/cyan]")


@shout_if_fails
@app.command("delete", help="Delete a constitution.")
def delete_constitution_command( # Renamed to avoid conflict with imported delete_constitution
    constitution_id: str = typer.Argument(
        ...,
        help=f"ID of the constitution to delete. Cannot delete 'none'. Disallowed chars: '{DISALLOWED_ID_CHARS}'"
    ),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Delete without confirmation"
    )
):
    if not constitution_manager._is_valid_id(constitution_id):
         console.print(f"[red]Invalid constitution ID '{constitution_id}'. Cannot contain: '{DISALLOWED_ID_CHARS}'[/red]")
         return

    if constitution_id == "none": # 'none' is a special case, often default
        console.print("[red]Cannot delete the special 'none' constitution placeholder.[/red]")
        return

    # Check if constitution exists before prompting for confirmation
    if constitution_manager.get_constitution_content(constitution_id) is None:
        console.print(f"[red]Constitution '{constitution_id}' not found.[/red]")
        return

    # Confirm deletion
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete constitution '{constitution_id}'?")
        if not confirm:
            console.print("[cyan]Deletion cancelled.[/cyan]")
            return

    # Delete constitution
    if constitution_manager.delete_constitution(constitution_id):
        console.print(f"[green]Constitution '{constitution_id}' deleted successfully.[/green]")
    else:
        # delete_constitution prints its own errors
        pass

# Interactive menu is removed as the commands are now handled directly in the main CLI loop
# def interactive_menu(): ...

if __name__ == "__main__":
    app()
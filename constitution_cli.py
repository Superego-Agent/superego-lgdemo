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

from constitution_manager import constitution_manager

# Create Typer app for constitution management
app = typer.Typer(help="Manage constitutions for the Superego system")
console = Console()

def get_editor() -> str:
    """Get the configured editor."""
    return os.environ.get("EDITOR", "nano")

@app.command("list")
def list_constitutions():
    """List all available constitutions."""
    constitutions = constitution_manager.get_available_constitutions()
    active_id = constitution_manager.get_active_constitution()
    
    # Create rich table
    table = Table(title="Available Constitutions")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="green")
    table.add_column("Size", justify="right", style="blue")
    table.add_column("Last Modified", style="magenta")
    
    for constitution in constitutions:
        # Mark active constitution with an asterisk
        id_text = f"* {constitution['id']}" if constitution["id"] == active_id else constitution["id"]
        # Format size
        size = f"{constitution['size'] / 1024:.1f} KB"
        # Format timestamp 
        import datetime
        last_modified = datetime.datetime.fromtimestamp(constitution["last_modified"]).strftime("%Y-%m-%d %H:%M")
        
        table.add_row(id_text, constitution["title"], size, last_modified)
    
    console.print("\n")
    console.print(table)
    console.print(f"\n* Current active constitution: [cyan]{active_id}[/cyan]\n")

@app.command("view")
def view_constitution(
    constitution_id: Optional[str] = typer.Argument(
        None, 
        help="ID of the constitution to view (defaults to active constitution)"
    )
):
    """View the content of a specific constitution."""
    if not constitution_id:
        constitution_id = constitution_manager.get_active_constitution()
    
    content = constitution_manager.get_constitution_content(constitution_id)
    if not content:
        console.print(f"[red]Constitution '{constitution_id}' not found.[/red]")
        return
    
    console.print(f"\n[cyan]CONSTITUTION: {constitution_id}[/cyan]")
    console.print(Panel(Markdown(content), title=constitution_id, border_style="cyan"))

@app.command("edit")
def edit_constitution(
    constitution_id: Optional[str] = typer.Argument(
        None, 
        help="ID of the constitution to edit (defaults to active constitution)"
    ),
    editor: Optional[str] = typer.Option(
        None, "--editor", "-e", 
        help="Editor to use (defaults to EDITOR env variable or nano)"
    )
):
    """Edit a constitution file."""
    if not constitution_id:
        constitution_id = constitution_manager.get_active_constitution()
    
    content = constitution_manager.get_constitution_content(constitution_id)
    if not content:
        console.print(f"[red]Constitution '{constitution_id}' not found.[/red]")
        return
    
    editor_to_use = editor or get_editor()
    console.print(f"[cyan]Editing constitution: {constitution_id}[/cyan]")
    console.print(f"[yellow]Opening in {editor_to_use}...[/yellow]")
    
    # Open in editor
    updated_content = constitution_manager.edit_in_temp_file(content, editor=editor_to_use)
    
    # Save updated content
    if constitution_manager.save_constitution(constitution_id, updated_content):
        console.print(f"[green]Constitution '{constitution_id}' saved successfully.[/green]")
        
        # Reload if this is the active constitution
        if constitution_id == constitution_manager.get_active_constitution():
            success, msg = constitution_manager.set_active_constitution(constitution_id)
            if success:
                console.print("[green]Active constitution reloaded.[/green]")
    else:
        console.print(f"[red]Failed to save constitution '{constitution_id}'.[/red]")

@app.command("create")
def create_new_constitution(
    constitution_id: str = typer.Argument(..., help="ID for the new constitution"),
    editor: Optional[str] = typer.Option(
        None, "--editor", "-e", 
        help="Editor to use (defaults to EDITOR env variable or nano)"
    )
):
    """Create a new constitution."""
    # Check if constitution already exists
    existing = constitution_manager.get_constitution_content(constitution_id)
    if existing:
        console.print(f"[red]Constitution '{constitution_id}' already exists.[/red]")
        return
    
    # Template for new constitutions
    template = "# New Constitution\n\nAdd your constitution rules here."
    
    editor_to_use = editor or get_editor()
    console.print(f"[cyan]Creating new constitution: {constitution_id}[/cyan]")
    console.print(f"[yellow]Opening in {editor_to_use}...[/yellow]")
    
    # Open in editor
    updated_content = constitution_manager.edit_in_temp_file(template, editor=editor_to_use)
    
    # Save new content
    if constitution_manager.save_constitution(constitution_id, updated_content):
        console.print(f"[green]Constitution '{constitution_id}' created successfully.[/green]")
    else:
        console.print(f"[red]Failed to create constitution '{constitution_id}'.[/red]")

@app.command("delete")
def delete_constitution(
    constitution_id: str = typer.Argument(..., help="ID of the constitution to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", 
        help="Delete without confirmation"
    )
):
    """Delete a constitution."""
    if constitution_id == "default":
        console.print("[red]Cannot delete the default constitution.[/red]")
        return
    
    if constitution_id == constitution_manager.get_active_constitution():
        console.print("[red]Cannot delete the active constitution. Switch to another constitution first.[/red]")
        return
    
    # Confirm deletion
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete '{constitution_id}'?")
        if not confirm:
            console.print("[cyan]Deletion cancelled.[/cyan]")
            return
    
    # Delete constitution
    if constitution_manager.delete_constitution(constitution_id):
        console.print(f"[green]Constitution '{constitution_id}' deleted successfully.[/green]")
    else:
        console.print(f"[red]Failed to delete constitution '{constitution_id}'.[/red]")

@app.command("switch")
def switch_constitution(
    constitution_id: str = typer.Argument(..., help="ID of the constitution to switch to")
):
    """Switch to a different constitution."""
    # Check if constitution exists
    if not constitution_manager.get_constitution_content(constitution_id):
        console.print(f"[red]Constitution '{constitution_id}' not found.[/red]")
        return
    
    # Switch to the specified constitution
    success, message = constitution_manager.set_active_constitution(constitution_id)
    if success:
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[red]{message}[/red]")

def interactive_menu():
    """Show interactive menu for managing constitutions."""
    
    # Define menu actions as functions to avoid the big if-elif chain
    def view_action():
        constitution_id = typer.prompt("Enter constitution ID to view (or press Enter for active)", default="")
        view_constitution(constitution_id if constitution_id else None)
    
    def edit_action():
        constitution_id = typer.prompt("Enter constitution ID to edit (or press Enter for active)", default="")
        edit_constitution(constitution_id if constitution_id else None)
    
    def create_action():
        constitution_id = typer.prompt("Enter ID for new constitution")
        if constitution_id:
            create_new_constitution(constitution_id)
        else:
            console.print("[red]Constitution ID is required.[/red]")
    
    def delete_action():
        constitution_id = typer.prompt("Enter constitution ID to delete")
        if constitution_id:
            delete_constitution(constitution_id)
        else:
            console.print("[red]Constitution ID is required.[/red]")
    
    def switch_action():
        constitution_id = typer.prompt("Enter constitution ID to switch to")
        if constitution_id:
            switch_constitution(constitution_id)
        else:
            console.print("[red]Constitution ID is required.[/red]")
    
    # Map menu options to their corresponding functions
    menu_options = {
        1: {"label": "View a constitution", "action": view_action},
        2: {"label": "Edit a constitution", "action": edit_action},
        3: {"label": "Create a new constitution", "action": create_action},
        4: {"label": "Delete a constitution", "action": delete_action},
        5: {"label": "Switch active constitution", "action": switch_action},
        6: {"label": "Return to main menu", "action": None},
    }
    
    while True:
        console.clear()
        console.print(Panel("[bold cyan]CONSTITUTION MANAGEMENT[/bold cyan]", border_style="cyan"))
        
        # Display available constitutions
        list_constitutions()
        
        # Show menu options
        console.print("[cyan]OPTIONS:[/cyan]")
        for key, option in menu_options.items():
            console.print(f"{key}. {option['label']}")
        
        # Get user choice
        choice = typer.prompt("\nEnter your choice", type=int, default=6)
        
        # Execute the selected action or exit
        if choice in menu_options:
            if choice == 6:  # Exit option
                break
                
            # Execute the function associated with this menu option
            menu_options[choice]["action"]()
            typer.prompt("Press Enter to continue", default="")
        else:
            console.print("[red]Invalid choice. Please enter a number from 1-6.[/red]")
            typer.prompt("Press Enter to continue", default="")

if __name__ == "__main__":
    app()

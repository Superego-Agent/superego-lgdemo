import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
from colorama import Fore, Style

# Import the core constitution functions from superego_core
from superego_core import (
    get_available_constitutions,
    get_constitution_content,
    save_constitution,
    delete_constitution,
    set_active_constitution,
    get_active_constitution
)

# Default editor for editing constitution files
DEFAULT_EDITOR = os.environ.get("EDITOR", "nano")

def format_constitutions_table(constitutions: List[Dict[str, Any]], active_id: str = None) -> str:
    """Format a list of constitutions as a nice table."""
    if not constitutions:
        return "No constitutions found."
    
    # Calculate column widths
    id_width = max(len("ID"), max(len(c["id"]) for c in constitutions))
    title_width = max(len("TITLE"), max(len(c["title"]) for c in constitutions))
    
    # Format header
    result = []
    header = f"| {'ID':<{id_width}} | {'TITLE':<{title_width}} |"
    divider = f"|{'-' * (id_width + 2)}|{'-' * (title_width + 2)}|"
    
    result.append(divider)
    result.append(header)
    result.append(divider)
    
    # Format rows
    for constitution in constitutions:
        # Mark active constitution with an asterisk
        marker = "* " if constitution["id"] == active_id else "  "
        row = f"|{marker}{constitution['id']:<{id_width-2}} | {constitution['title']:<{title_width}} |"
        result.append(row)
    
    result.append(divider)
    result.append(f"* Current active constitution: {active_id}")
    
    return "\n".join(result)

def edit_in_temp_file(content: str, suffix: str = ".md", editor: str = DEFAULT_EDITOR) -> str:
    """Edit content in a temporary file using the system editor."""
    with tempfile.NamedTemporaryFile(suffix=suffix, mode="w+", delete=False) as temp:
        temp.write(content)
        temp_filename = temp.name
    
    try:
        # Open the editor with the temp file
        subprocess.run([editor, temp_filename], check=True)
        
        # Read the updated content
        with open(temp_filename, "r") as temp:
            return temp.read()
    finally:
        # Clean up the temp file
        os.unlink(temp_filename)

def list_constitutions():
    """List all available constitutions."""
    constitutions = get_available_constitutions()
    active_id = get_active_constitution()
    
    # Print formatted table
    print(Fore.CYAN + "\nAVAILABLE CONSTITUTIONS:")
    print(format_constitutions_table(constitutions, active_id))
    print()

def view_constitution(constitution_id: str = None):
    """View the content of a specific constitution."""
    if not constitution_id:
        constitution_id = get_active_constitution()
    
    content = get_constitution_content(constitution_id)
    if not content:
        print(Fore.RED + f"Constitution '{constitution_id}' not found.")
        return
    
    print(Fore.CYAN + f"\nCONSTITUTION: {constitution_id}")
    print(Fore.CYAN + "=" * 60)
    print(Fore.WHITE + content)
    print(Fore.CYAN + "=" * 60 + "\n")

def edit_constitution(constitution_id: str = None, editor: str = DEFAULT_EDITOR):
    """Edit a constitution file."""
    if not constitution_id:
        constitution_id = get_active_constitution()
    
    content = get_constitution_content(constitution_id)
    if not content:
        print(Fore.RED + f"Constitution '{constitution_id}' not found.")
        return
    
    print(Fore.CYAN + f"Editing constitution: {constitution_id}")
    print(Fore.YELLOW + f"Opening in {editor}...")
    
    # Open in editor
    updated_content = edit_in_temp_file(content, editor=editor)
    
    # Save updated content
    if save_constitution(constitution_id, updated_content):
        print(Fore.GREEN + f"Constitution '{constitution_id}' saved successfully.")
        
        # Reload if this is the active constitution
        if constitution_id == get_active_constitution():
            set_active_constitution(constitution_id)
            print(Fore.GREEN + "Active constitution reloaded.")
    else:
        print(Fore.RED + f"Failed to save constitution '{constitution_id}'.")

def create_new_constitution(constitution_id: str, editor: str = DEFAULT_EDITOR):
    """Create a new constitution."""
    # Check if constitution already exists
    existing = get_constitution_content(constitution_id)
    if existing:
        print(Fore.RED + f"Constitution '{constitution_id}' already exists.")
        return
    
    # Template for new constitutions
    template = f"""# {constitution_id.title()} Constitution

## Core Principles
Universal Ethical Floor: Always prioritise preventing harm and upholding fundamental human rights.

## Harm Detection Framework
Direct Harm Prevention: Block requests that could lead to harm.

## Balanced Implementation
Proportional Response: Scale scrutiny based on risk level.
"""
    
    print(Fore.CYAN + f"Creating new constitution: {constitution_id}")
    print(Fore.YELLOW + f"Opening in {editor}...")
    
    # Open in editor
    updated_content = edit_in_temp_file(template, editor=editor)
    
    # Save new content
    if save_constitution(constitution_id, updated_content):
        print(Fore.GREEN + f"Constitution '{constitution_id}' created successfully.")
    else:
        print(Fore.RED + f"Failed to create constitution '{constitution_id}'.")

def delete_constitution_cmd(constitution_id: str):
    """Delete a constitution."""
    if constitution_id == "default":
        print(Fore.RED + "Cannot delete the default constitution.")
        return
    
    if constitution_id == get_active_constitution():
        print(Fore.RED + "Cannot delete the active constitution. Switch to another constitution first.")
        return
    
    # Confirm deletion
    confirm = input(Fore.YELLOW + f"Are you sure you want to delete '{constitution_id}'? (y/N): ")
    if confirm.lower() != 'y':
        print(Fore.CYAN + "Deletion cancelled.")
        return
    
    # Delete constitution
    if delete_constitution(constitution_id):
        print(Fore.GREEN + f"Constitution '{constitution_id}' deleted successfully.")
    else:
        print(Fore.RED + f"Failed to delete constitution '{constitution_id}'.")

def switch_constitution(constitution_id: str):
    """Switch to a different constitution."""
    # Check if constitution exists
    if not get_constitution_content(constitution_id):
        print(Fore.RED + f"Constitution '{constitution_id}' not found.")
        return
    
    # Switch to the specified constitution
    if set_active_constitution(constitution_id):
        print(Fore.GREEN + f"Switched to constitution: {constitution_id}")
    else:
        print(Fore.RED + f"Failed to switch to constitution '{constitution_id}'.")

def constitution_menu(editor: str = DEFAULT_EDITOR):
    """Show interactive menu for managing constitutions."""
    while True:
        print(Fore.CYAN + "\n" + "=" * 60)
        print(Fore.CYAN + "CONSTITUTION MANAGEMENT")
        print(Fore.CYAN + "=" * 60)
        
        # Display available constitutions
        constitutions = get_available_constitutions()
        active_id = get_active_constitution()
        print(format_constitutions_table(constitutions, active_id))
        
        # Show menu options
        print(Fore.CYAN + "\nOPTIONS:")
        print(Fore.WHITE + "1. View a constitution")
        print(Fore.WHITE + "2. Edit a constitution")
        print(Fore.WHITE + "3. Create a new constitution")
        print(Fore.WHITE + "4. Delete a constitution")
        print(Fore.WHITE + "5. Switch active constitution")
        print(Fore.WHITE + "6. Return to main menu")
        
        choice = input(Fore.YELLOW + "\nEnter your choice (1-6): ")
        
        if choice == "1":
            constitution_id = input(Fore.YELLOW + "Enter constitution ID to view (or press Enter for active): ")
            view_constitution(constitution_id if constitution_id else None)
        
        elif choice == "2":
            constitution_id = input(Fore.YELLOW + "Enter constitution ID to edit (or press Enter for active): ")
            edit_constitution(constitution_id if constitution_id else None, editor=editor)
        
        elif choice == "3":
            constitution_id = input(Fore.YELLOW + "Enter ID for new constitution: ")
            if constitution_id:
                create_new_constitution(constitution_id, editor=editor)
            else:
                print(Fore.RED + "Constitution ID is required.")
        
        elif choice == "4":
            constitution_id = input(Fore.YELLOW + "Enter constitution ID to delete: ")
            if constitution_id:
                delete_constitution_cmd(constitution_id)
            else:
                print(Fore.RED + "Constitution ID is required.")
        
        elif choice == "5":
            constitution_id = input(Fore.YELLOW + "Enter constitution ID to switch to: ")
            if constitution_id:
                switch_constitution(constitution_id)
            else:
                print(Fore.RED + "Constitution ID is required.")
        
        elif choice == "6":
            break
        
        else:
            print(Fore.RED + "Invalid choice. Please enter a number from 1-6.")

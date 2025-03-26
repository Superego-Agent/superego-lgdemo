# constitution_manager.py
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import re

from config import CONFIG
from utils import shout_if_fails

# Disallowed characters in constitution IDs
DISALLOWED_ID_CHARS = "+[] ," # Banning '+' for composition, '[] ,' for compare lists

class ConstitutionManager:
    """Core manager for constitutions with no UI dependencies."""

    def __init__(self, constitutions_dir: str = CONFIG["constitutions_dir"]):
        self.constitutions_dir = Path(constitutions_dir)
        self.constitutions_dir.mkdir(parents=True, exist_ok=True)
        self.default_editor = os.environ.get("EDITOR", "nano")

    def _is_valid_id(self, constitution_id: str) -> bool:
        """Check if the constitution ID is valid."""
        if not constitution_id or any(char in constitution_id for char in DISALLOWED_ID_CHARS):
            return False
        # Basic filesystem path safety (simplified)
        return not ("/" in constitution_id or "\\" in constitution_id or ".." in constitution_id)

    def get_available_constitutions(self) -> List[Dict[str, Any]]:
        """List all available constitutions with metadata."""
        result = []

        for constitution_path in self.constitutions_dir.glob("*.md"):
            constitution_id = constitution_path.stem
            if not self._is_valid_id(constitution_id):
                continue # Skip invalid IDs

            try:
                with open(constitution_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    # Try to extract title from first line (e.g., "# My Title")
                    title_match = re.match(r"^#+\s*(.*)", first_line)
                    title = title_match.group(1).strip() if title_match else constitution_id

                    stats = constitution_path.stat()
                    result.append({
                        "id": constitution_id,
                        "title": title,
                        "path": str(constitution_path),
                        "size": stats.st_size,
                        "last_modified": stats.st_mtime
                    })
            except Exception as e:
                result.append({
                    "id": constitution_id,
                    "title": f"{constitution_id} (Error)",
                    "path": str(constitution_path),
                    "error": str(e)
                })

        result.sort(key=lambda x: x["id"])
        return result

    def get_constitution_content(self, constitution_id: str) -> Optional[str]:
        """Get the content of a single specific constitution."""
        if not self._is_valid_id(constitution_id):
            return None
        constitution_path = self.constitutions_dir / f"{constitution_id}.md"

        if not constitution_path.exists():
            return None

        try:
            with open(constitution_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    @shout_if_fails
    def get_combined_constitution_content(self, constitution_ids: List[str]) -> Tuple[str, List[str]]:
        """
        Gets and concatenates content from multiple constitutions.
        Returns the combined content and a list of the IDs successfully loaded.
        """
        combined_content = ""
        loaded_ids = []
        separator = "\n\n---\n\n" # Separator between combined constitutions

        for const_id in constitution_ids:
            content = self.get_constitution_content(const_id)
            if content is not None:
                if combined_content: # Add separator if not the first constitution
                    combined_content += separator
                combined_content += f"## Constitution Section: {const_id}\n\n{content}"
                loaded_ids.append(const_id)
            else:
                # Optionally log or signal that a constitution couldn't be loaded
                print(f"[yellow]Warning: Constitution '{const_id}' not found or couldn't be loaded.[/yellow]")
                pass

        return combined_content, loaded_ids


    def save_constitution(self, constitution_id: str, content: str) -> bool:
        """Save a constitution (create new or update existing)."""
        if not self._is_valid_id(constitution_id):
             print(f"[red]Error: Invalid constitution ID '{constitution_id}'. Cannot contain: {DISALLOWED_ID_CHARS}[/red]")
             return False
        constitution_path = self.constitutions_dir / f"{constitution_id}.md"

        try:
            with open(constitution_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"[red]Error saving constitution '{constitution_id}': {e}[/red]")
            return False

    def delete_constitution(self, constitution_id: str) -> bool:
        """Delete a constitution."""
        if not self._is_valid_id(constitution_id):
             return False # Should not happen if called from CLI which validates

        constitution_path = self.constitutions_dir / f"{constitution_id}.md"

        if not constitution_path.exists():
            return False

        try:
            constitution_path.unlink()
            return True
        except Exception as e:
            print(f"[red]Error deleting constitution '{constitution_id}': {e}[/red]")
            return False

    @shout_if_fails
    def edit_in_temp_file(self, content: str, suffix: str = ".md", editor: str = None) -> Optional[str]:
        """Edit content in a temporary file using the system editor. Returns updated content or None if edit failed/aborted."""
        if editor is None:
            editor = self.default_editor

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, mode="w+", delete=False, encoding='utf-8') as temp:
                temp.write(content)
                temp_filename = temp.name

            # Open the editor with the temp file
            result = subprocess.run([editor, temp_filename]) # Let potential errors propagate

            if result.returncode != 0:
                 print(f"[yellow]Editor exited with code {result.returncode}. Assuming no changes.[/yellow]")
                 return None # Indicate no changes or aborted edit

            # Read the updated content
            with open(temp_filename, "r", encoding='utf-8') as temp:
                updated_content = temp.read()

            # Only return content if it actually changed
            return updated_content if updated_content != content else None

        finally:
            # Clean up the temp file
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                except Exception as e:
                    print(f"[yellow]Warning: Failed to delete temp file {temp_filename}: {e}[/yellow]")

# Create a global instance for easy access
constitution_manager = ConstitutionManager()
import os
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from config import CONFIG

class ConstitutionManager:
    """Core manager for constitutions with no UI dependencies."""
    
    def __init__(self, constitutions_dir: str = CONFIG["constitutions_dir"]):
        self.constitutions_dir = Path(constitutions_dir)
        self.constitutions_dir.mkdir(parents=True, exist_ok=True)
        self.default_editor = os.environ.get("EDITOR", "nano")
        
    def get_available_constitutions(self) -> List[Dict[str, Any]]:
        """List all available constitutions with metadata."""
        result = []
        
        for constitution_path in self.constitutions_dir.glob("*.md"):
            # Get the file name without extension as the constitution ID
            constitution_id = constitution_path.stem
            
            # Read first line to extract title (assumes first line is a markdown title)
            try:
                with open(constitution_path, 'r') as f:
                    first_line = f.readline().strip()
                    title = first_line.replace('#', '').strip()
                    
                    # Get file size and last modified time
                    stats = constitution_path.stat()
                    
                    result.append({
                        "id": constitution_id,
                        "title": title,
                        "path": str(constitution_path),
                        "size": stats.st_size,
                        "last_modified": stats.st_mtime
                    })
            except Exception as e:
                # If there's an error reading the file, still include it with minimal info
                result.append({
                    "id": constitution_id,
                    "title": constitution_id,
                    "path": str(constitution_path),
                    "error": str(e)
                })
        
        # Sort by title
        result.sort(key=lambda x: x["title"])
        return result

    def get_constitution_content(self, constitution_id: str) -> Optional[str]:
        """Get the content of a specific constitution."""
        constitution_path = self.constitutions_dir / f"{constitution_id}.md"
        
        if not constitution_path.exists():
            return None
            
        try:
            with open(constitution_path, 'r') as f:
                return f.read()
        except Exception:
            return None

    def save_constitution(self, constitution_id: str, content: str) -> bool:
        """Save a constitution (create new or update existing)."""
        constitution_path = self.constitutions_dir / f"{constitution_id}.md"
        
        try:
            with open(constitution_path, 'w') as f:
                f.write(content)
            return True
        except Exception:
            return False

    def delete_constitution(self, constitution_id: str) -> bool:
        """Delete a constitution."""
        # Don't allow deleting default constitution
        if constitution_id == "default":
            return False
            
        constitution_path = self.constitutions_dir / f"{constitution_id}.md"
        
        if not constitution_path.exists():
            return False
            
        try:
            constitution_path.unlink()
            return True
        except Exception:
            return False

    def get_active_constitution(self) -> str:
        """Get the currently active constitution ID."""
        constitution_path = Path(CONFIG["file_paths"]["constitution"])
        return constitution_path.stem

    def set_active_constitution(self, constitution_id: str) -> Tuple[bool, str]:
        """Set the active constitution for the application."""
        constitution_path = self.constitutions_dir / f"{constitution_id}.md"
        
        if not constitution_path.exists():
            return False, f"Constitution '{constitution_id}' not found"
            
        # Update the config
        CONFIG["file_paths"]["constitution"] = str(constitution_path)
        
        # Force reload of instructions in superego_core
        from superego_core import reload_instructions
        reload_instructions()
        
        return True, f"Switched to constitution: {constitution_id}"

    def edit_in_temp_file(self, content: str, suffix: str = ".md", editor: str = None) -> str:
        """Edit content in a temporary file using the system editor."""
        if editor is None:
            editor = self.default_editor
            
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

    def format_constitutions_table(self, active_id: str = None) -> str:
        """Format a list of constitutions as a text table."""
        constitutions = self.get_available_constitutions()
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
        if active_id:
            result.append(f"* Current active constitution: {active_id}")
        
        return "\n".join(result)

# Create a global instance for easy access
constitution_manager = ConstitutionManager()

# constitution_utils.py
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Assuming config.py and utils.py (with shout_if_fails) exist in the same dir
from config import CONFIG
from utils import shout_if_fails

# Disallowed characters in constitution IDs (includes space, '+')
DISALLOWED_ID_CHARS = "+[] ,"

CONSTITUTIONS_DIR = Path(CONFIG.get("constitutions_dir", "data/constitutions"))
CONSTITUTIONS_DIR.mkdir(parents=True, exist_ok=True)


def _is_valid_id_format(constitution_id: str) -> bool:
    """Checks if ID format prevents parsing issues (no space, no '+')."""
    return constitution_id and not any(char in constitution_id for char in DISALLOWED_ID_CHARS) \
           and not ("/" in constitution_id or "\\" in constitution_id or ".." in constitution_id)


@shout_if_fails # Let decorator handle unexpected I/O errors
def get_available_constitutions() -> Dict[str, Dict[str, Any]]:
    """Lists available constitutions found in the constitutions directory."""
    result = {"none": {"filename": "[i]N/A[/i]", "description": "[i]No constitution.[/i]"}}
    for constitution_path in CONSTITUTIONS_DIR.glob("*.md"):
        constitution_id = constitution_path.stem
        if not _is_valid_id_format(constitution_id) or constitution_id == "none":
            continue

        # Minimal read to get description from first line (if any)
        try:
            with open(constitution_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                title_match = re.match(r"^#+\s*(.*)", first_line)
                description = title_match.group(1).strip() if title_match else f"'{constitution_id}'"
        except Exception:
            # Fallback if file read fails unexpectedly (though shout_if_fails might catch it earlier)
            description = f"[red]Error reading {constitution_path.name}[/red]"

        result[constitution_id] = {
            "filename": constitution_path.name,
            "description": description,
        }
    return result


def get_constitution_content(constitution_id: str) -> Optional[str]:
    """Reads content of a single constitution; returns None if not found/invalid."""
    if constitution_id == "none":
        return ""
    if not _is_valid_id_format(constitution_id):
        return None # Invalid format cannot exist
    constitution_path = CONSTITUTIONS_DIR / f"{constitution_id}.md"
    try:
        with open(constitution_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None 


@shout_if_fails 
def get_combined_constitution_content(constitution_ids: List[str]) -> Tuple[str, List[str]]:
    """Combines content from multiple valid constitutions."""
    if "none" in constitution_ids:
        return "", ["none"]

    combined_content = ""
    loaded_ids = []
    separator = "\n\n---\n\n"
    # Use set for unique IDs, ignore format check here assuming validated input
    unique_ids = sorted(list(set(id for id in constitution_ids if id)))

    for const_id in unique_ids:
        content = get_constitution_content(const_id)
        if content is not None: # Content exists and was read
            if combined_content:
                combined_content += separator
            # Add simple header for clarity when combining multiple
            combined_content += f"## Constitution Section: {const_id}\n\n{content}"
            loaded_ids.append(const_id)

    # Return 'none' convention if no valid content was loaded
    return (combined_content, loaded_ids) if loaded_ids else ("", ["none"])
import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import frontmatter # For parsing YAML frontmatter
from config import CONFIG
from utils import shout_if_fails

# Disallowed characters in constitution IDs (includes space, '+')
DISALLOWED_ID_CHARS = "+[] ,"

CONSTITUTIONS_DIR = Path(CONFIG.get("constitutions_dir", "data/constitutions"))
CONSTITUTIONS_DIR.mkdir(parents=True, exist_ok=True)

# Setup basic logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')


def _is_valid_id_format(constitution_id: str) -> bool:
    """Checks if ID format prevents parsing issues (no space, no '+')."""
    return constitution_id and not any(char in constitution_id for char in DISALLOWED_ID_CHARS) \
           and not ("/" in constitution_id or "\\" in constitution_id or ".." in constitution_id)


@shout_if_fails
def get_available_constitutions() -> Dict[str, Dict[str, Any]]:
    """
    Lists available constitutions by parsing YAML frontmatter from .md files.
    Returns a dictionary mapping constitution ID to its metadata (title, description).
    """
    result = {"none": {"title": "None", "description": "No constitution selected."}}
    for constitution_path in CONSTITUTIONS_DIR.glob("*.md"):
        constitution_id = constitution_path.stem
        if not _is_valid_id_format(constitution_id) or constitution_id == "none":
            continue

        # Removed logging.info(f"Processing constitution file: ...")
        try:
            post = frontmatter.load(constitution_path)
            # Removed logging.info(f"Successfully loaded: ...")
            title = post.metadata.get('title', constitution_id.replace('_', ' ').title())
            description = post.metadata.get('description', '')

            if not post.metadata.get('title') or not post.metadata.get('description'):
                 logging.warning(f"Constitution '{constitution_path.name}' is missing 'title' or 'description' in YAML frontmatter. Falling back to defaults.")

            result[constitution_id] = {
                "title": title,
                "description": description,
                # Keep filename for potential future use, though title is primary now
                "filename": constitution_path.name
            }
        except Exception as e:
            logging.error(f"Error parsing frontmatter for {constitution_path.name}: {e}")
            # Provide a fallback entry indicating the error
            result[constitution_id] = {
                "title": f"{constitution_id} (Error)",
                "description": f"Error loading constitution: {e}",
                "filename": constitution_path.name
            }
    return result


def get_constitution_content(constitution_id: str) -> Optional[str]:
    """
    Reads the main content (after YAML frontmatter) of a single constitution.
    Returns None if not found, invalid ID, or parsing error occurs.
    """
    if constitution_id == "none":
        return "" # Return empty string for 'none' constitution
    if not _is_valid_id_format(constitution_id):
        logging.warning(f"Invalid constitution ID format requested: {constitution_id}")
        return None
    constitution_path = CONSTITUTIONS_DIR / f"{constitution_id}.md"
    if not constitution_path.is_file():
        logging.warning(f"Constitution file not found: {constitution_path}")
        return None

    try:
        post = frontmatter.load(constitution_path)
        return post.content
    except FileNotFoundError: # Should be caught by is_file, but belt-and-suspenders
         logging.error(f"File not found during frontmatter load (unexpected): {constitution_path}")
         return None
    except Exception as e:
        logging.error(f"Error parsing frontmatter or reading content for {constitution_path.name}: {e}")
        return None


@shout_if_fails 
def get_combined_constitution_content(constitution_ids: List[str]) -> Tuple[str, List[str]]:
    """Combines content from multiple valid constitutions."""
    if "none" in constitution_ids:
        return "", ["none"]

    combined_content = ""
    loaded_ids = []
    separator = "\n\n---\n\n"
    unique_ids = sorted(list(set(id for id in constitution_ids if id)))

    for const_id in unique_ids:
        content = get_constitution_content(const_id)
        if content is not None:
            if combined_content:
                combined_content += separator
            combined_content += content
            loaded_ids.append(const_id)

    return (combined_content, loaded_ids) if loaded_ids else ("", ["none"])

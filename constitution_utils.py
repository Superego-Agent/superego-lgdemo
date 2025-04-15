import os
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import frontmatter # For parsing YAML frontmatter
from config import CONFIG
from utils import shout_if_fails # Keep for get_combined_constitution_content if needed

# Import new models
from backend_models import (
    ConstitutionHierarchy,
    ConstitutionFolder,
    RemoteConstitutionMetadata,
)

CONSTITUTIONS_DIR = Path(CONFIG.get("constitutions_dir", "data/constitutions")).resolve()
CONSTITUTIONS_DIR.mkdir(parents=True, exist_ok=True)

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_constitution_hierarchy() -> ConstitutionHierarchy:
    """
    Scans the CONSTITUTIONS_DIR recursively to build a hierarchical structure
    of constitution folders and files based on their frontmatter metadata.

    Returns:
        ConstitutionHierarchy: The root object representing the hierarchy.
    """
    root_folders_dict: Dict[str, ConstitutionFolder] = {} # Temp dict for building
    root_constitutions: List[RemoteConstitutionMetadata] = []
    folder_map: Dict[str, ConstitutionFolder] = {} # Map relative_path -> folder object

    for md_path in CONSTITUTIONS_DIR.rglob("*.md"):
        try:
            # Calculate relative path (use forward slashes)
            relative_path_obj = md_path.relative_to(CONSTITUTIONS_DIR)
            relative_path_str = relative_path_obj.as_posix()
            filename = md_path.name

            # Parse frontmatter
            post = frontmatter.load(md_path)
            title = post.metadata.get('title', filename.replace('.md', '').replace('_', ' ').title())
            description = post.metadata.get('description')

            metadata = RemoteConstitutionMetadata(
                title=title,
                description=description,
                relativePath=relative_path_str,
                filename=filename
            )

            # --- Build Hierarchy ---
            parent_rel_path = relative_path_obj.parent.as_posix()
            if parent_rel_path == '.': # Root level constitution
                root_constitutions.append(metadata)
            else:
                # Ensure parent folders exist up to the root
                current_parent_rel_path = ""
                parent_folder_obj = None
                for i, part in enumerate(relative_path_obj.parent.parts):
                    folder_rel_path = "/".join(relative_path_obj.parent.parts[:i+1])
                    if folder_rel_path not in folder_map:
                        new_folder = ConstitutionFolder(
                            folderTitle=part.replace('_', ' ').title(),
                            relativePath=folder_rel_path
                        )
                        folder_map[folder_rel_path] = new_folder
                        # Link to its parent
                        if current_parent_rel_path and current_parent_rel_path in folder_map:
                            folder_map[current_parent_rel_path].subFolders.append(new_folder)
                        elif i == 0: # It's a root folder
                             root_folders_dict[part] = new_folder # Add to root dict

                    parent_folder_obj = folder_map[folder_rel_path]
                    current_parent_rel_path = folder_rel_path # Update for next level

                # Add constitution to its direct parent folder
                if parent_folder_obj:
                    parent_folder_obj.constitutions.append(metadata)
                else:
                     logger.error(f"Logic error: Could not find/create parent folder for constitution '{relative_path_str}'")


        except Exception as e:
            logger.error(f"Error processing constitution file {md_path.name}: {e}", exc_info=True)
            # Optionally skip this file or add an error marker

    # --- Sorting ---
    def sort_folder_contents(folder: ConstitutionFolder):
        # Sort subfolders alphabetically by folderTitle
        folder.subFolders.sort(key=lambda f: f.folderTitle)
        # Sort constitutions alphabetically by filename
        folder.constitutions.sort(key=lambda c: c.filename)
        # Recursively sort subfolders
        for sub_folder in folder.subFolders:
            sort_folder_contents(sub_folder)

    # Sort root level
    root_constitutions.sort(key=lambda c: c.filename)
    # Convert root_folders dict to list and sort alphabetically by folderTitle
    sorted_root_folders = sorted(root_folders_dict.values(), key=lambda f: f.folderTitle)

    # Recursively sort contents of each root folder
    for folder in sorted_root_folders:
        sort_folder_contents(folder)

    return ConstitutionHierarchy(
        rootConstitutions=root_constitutions,
        rootFolders=sorted_root_folders
    )


def get_constitution_content(relativePath: str) -> Optional[str]:
    """
    Reads the main content (after YAML frontmatter) of a single constitution
    identified by its relative path from the CONSTITUTIONS_DIR.

    Args:
        relativePath: The path relative to CONSTITUTIONS_DIR, e.g., "folder/file.md".

    Returns:
        Optional[str]: The content of the constitution, or None if not found,
                       access is denied due to security checks, or a parsing error occurs.
    """
    # Basic validation for path components
    if not relativePath or \
       any(part in ('', '.', '..') for part in Path(relativePath).parts) or \
       os.path.isabs(relativePath):
        logger.warning(f"Invalid relative path format requested: {relativePath}")
        return None

    try:
        # Construct the full path relative to CONSTITUTIONS_DIR
        # Normalizing ensures consistent path separators and removes redundant parts like './'
        # but doesn't resolve symlinks or '..' components fully like resolve()
        # We rely on the initial check and the final check after resolving
        normalized_rel_path = os.path.normpath(relativePath)
        # Re-check after normalization
        if any(part in ('', '.', '..') for part in Path(normalized_rel_path).parts) or \
           os.path.isabs(normalized_rel_path):
             logger.warning(f"Invalid relative path format after normalization: {normalized_rel_path} (from {relativePath})")
             return None

        full_path = (CONSTITUTIONS_DIR / normalized_rel_path).resolve()


        # --- Security Check ---
        # Ensure the resolved path is still within the CONSTITUTIONS_DIR or is CONSTITUTIONS_DIR itself
        # Using os.path.commonpath is a robust way to check containment
        common_path = os.path.commonpath([str(CONSTITUTIONS_DIR), str(full_path)])
        if common_path != str(CONSTITUTIONS_DIR):
            logger.warning(
                f"Security Alert: Attempted path traversal detected. "
                f"Requested relativePath '{relativePath}' resolved to '{full_path}', "
                f"which is outside the allowed directory '{CONSTITUTIONS_DIR}'."
            )
            return None

        if not full_path.is_file():
            # Log as warning, as frontend might request non-existent paths during exploration
            logger.warning(f"Constitution file not found at resolved path: {full_path} (from relative: {relativePath})")
            return None

        # Load content using frontmatter
        post = frontmatter.load(full_path)
        return post.content

    except FileNotFoundError:
        # This might occur if the file exists during resolve() but is deleted before load()
        logger.error(f"Constitution file not found during load (unexpected): {full_path} (from relative: {relativePath})")
        return None
    except Exception as e:
        # Catch broader exceptions during file operations or parsing
        logger.error(f"Error parsing frontmatter or reading content for {relativePath} (resolved: {full_path}): {e}", exc_info=True)
        return None


# Keep the decorator if external systems rely on the exception bubbling up
# If not, standard error handling + logging + returning None might be sufficient
@shout_if_fails
def get_combined_constitution_content(relativePaths: List[str]) -> Tuple[str, List[str]]:
    """
    Combines content from multiple valid constitutions identified by their relative paths.
    Handles potential duplicates and ensures a consistent separator.

    Args:
        relativePaths: A list of relative paths for the constitutions to combine.

    Returns:
        Tuple[str, List[str]]: A tuple containing the combined content string
                               and a list of the relative paths successfully loaded.
                               Returns ("", []) if no valid paths are provided or loaded.
    """
    # Filter out empty strings, "none", or other invalid placeholders upfront
    valid_paths_input = [p for p in relativePaths if p and p != "none"]

    if not valid_paths_input:
        return "", []

    combined_content = ""
    loaded_paths = []
    separator = "\n\n---\n\n"
    # Use set for uniqueness, then sort for deterministic order
    unique_paths = sorted(list(set(valid_paths_input)))

    for rel_path in unique_paths:
        content = get_constitution_content(rel_path) # Use the updated function
        if content is not None: # Check for None explicitly
            if combined_content:
                combined_content += separator
            combined_content += content
            loaded_paths.append(rel_path)
        else:
             # Log failure to load a specific constitution
             logger.warning(f"Could not load content for constitution path: {rel_path}")


    # Return empty string and empty list if nothing was loaded successfully
    return (combined_content, loaded_paths) if loaded_paths else ("", [])

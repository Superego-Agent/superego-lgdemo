from fastmcp import FastMCP

# from mcp.server.fastmcp import FastMCP
from constitution_utils import get_constitution_content, get_constitution_hierarchy

# Create an MCP server
mcp = FastMCP("Constitution Server", host="0.0.0.0", port=8080)


def list_constitutions() -> list:
    """List all available constitutions"""
    constitutionsHierarchy = get_constitution_hierarchy()
    items = constitutionsHierarchy.rootConstitutions
    return [{"title": item.title, "description": item.description} for item in items]


def search_constitution(keyword: str) -> str:
    """Search for constitutions by keyword.
    The keyword can be any title from the list of constitutions such as 'vegan' or 'child protection context'"""
    if not keyword:
        raise ValueError("keyword parameter is required")

    keyword = str(keyword).lower()

    # Get the full hierarchy
    hierarchy = get_constitution_hierarchy()

    # Helper function to search recursively through folders
    def find_constitution_by_keyword(keyword: str, folder) -> str | None:
        # Check constitutions in current folder
        for const in folder.constitutions:
            if keyword in const.title.lower() or (
                const.description and keyword in const.description.lower()
            ):
                return const.relativePath
        # Recursively check subfolders
        for subfolder in folder.subFolders:
            result = find_constitution_by_keyword(keyword, subfolder)
            if result:
                return result
        return None

    # First check root constitutions
    relative_path = None
    for const in hierarchy.rootConstitutions:
        if keyword in const.title.lower() or (
            const.description and keyword in const.description.lower()
        ):
            relative_path = const.relativePath
            break

    # If not found in root, search through folders
    if not relative_path:
        for folder in hierarchy.rootFolders:
            relative_path = find_constitution_by_keyword(keyword, folder)
            if relative_path:
                break

    if not relative_path:
        raise ValueError(f"No constitution found matching keyword '{keyword}'")

    # Get the content using the found relative path
    content = get_constitution_content(relative_path)
    if content is None:
        raise ValueError(
            f"Failed to load content for constitution matching '{keyword}'"
        )

    return content


# Register resources
mcp.add_resource_fn(list_constitutions, uri="constitutions://list")
mcp.add_resource_fn(search_constitution, uri="constitutions://search/{keyword}")

if __name__ == "__main__":
    mcp.run()

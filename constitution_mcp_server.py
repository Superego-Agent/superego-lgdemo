from mcp.server.fastmcp import FastMCP
from constitution_utils import (
    get_constitution_hierarchy,
)

# Create an MCP server
app = FastMCP("Constitution Server")

@app.resource("constitutions://list")
def list_constitutions() -> list:
    """List all available constitutions"""
    constitutionsHierarchy = get_constitution_hierarchy()
    items = constitutionsHierarchy.rootConstitutions
    return [{"title": item.title, "description": item.description} for item in items]

if __name__ == "__main__":
    app.run() 
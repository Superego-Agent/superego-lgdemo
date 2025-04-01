from pathlib import Path
from typing import Dict, List, Optional
import asyncio

from mcp.server.fastmcp import FastMCP
from mcp.server import stdio
from constitution_utils import (
    get_available_constitutions,
    get_constitution_content,
    get_combined_constitution_content,
)

# Create an MCP server
app = FastMCP("Constitution Server")

@app.resource("constitutions://list")
def list_constitutions() -> str:
    """List all available constitutions"""
    constitutions = get_available_constitutions()
    print(f"Constitutions: {constitutions}")
    return "\n".join([f"- {k}: {v}" for k, v in constitutions.items()])

@app.resource("constitutions://{constitution_id}")
def get_constitution(constitution_id: str) -> str:
    """Get a specific constitution by ID"""
    content = get_constitution_content(constitution_id)
    if content is None:
        raise ValueError(f"Constitution {constitution_id} not found")
    return content

@app.resource("constitutions://combine/{constitution_ids}")
def combine_constitutions(constitution_ids: str) -> str:
    """Combine multiple constitutions (IDs separated by '+')"""
    ids = constitution_ids.split('+')
    content, loaded_ids = get_combined_constitution_content(ids)
    if not loaded_ids:
        raise ValueError("No valid constitutions found")
    return f"Combined constitutions ({', '.join(loaded_ids)}):\n\n{content}"

if __name__ == "__main__":
    app.run() 
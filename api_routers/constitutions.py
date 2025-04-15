# api_routers/constitutions.py
import logging
import traceback
from typing import List
from fastapi import APIRouter, HTTPException, Path as FastApiPath
from fastapi.responses import PlainTextResponse

# Project-specific imports
from backend_models import ConstitutionHierarchy
try:
    from constitution_utils import get_constitution_hierarchy, get_constitution_content
except ImportError as e:
    print(f"Error importing constitution_utils in constitutions router: {e}")
    # Handle appropriately, maybe raise an error or log
    raise

router = APIRouter()

@router.get("/api/constitutions", response_model=ConstitutionHierarchy)
async def get_constitutions_endpoint():
    """Returns a hierarchical structure of available constitutions."""
    try:
        # Call the new utility function that returns the hierarchy directly
        hierarchy = get_constitution_hierarchy()
        return hierarchy
    except Exception as e:
        logging.error(f"Error loading constitutions in endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load constitutions: {str(e)}")

@router.get("/api/constitutions/{relativePath:path}/content", response_model=str)
async def get_constitution_content_endpoint(
    relativePath: str = FastApiPath(..., title="The relative path of the constitution")
):
    """Returns the raw text content of a single constitution."""
    try:
        content = get_constitution_content(relativePath)
        if content is None:
            raise HTTPException(status_code=404, detail=f"Constitution '{relativePath}' not found or invalid.")
        return PlainTextResponse(content=content)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting content for constitution {relativePath}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load content for constitution '{relativePath}'.")

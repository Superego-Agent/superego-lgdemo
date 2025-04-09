# api_routers/constitutions.py
import logging
import traceback
from typing import List
from fastapi import APIRouter, HTTPException, Path as FastApiPath
from fastapi.responses import PlainTextResponse

# Project-specific imports
from backend_models import ConstitutionItem
try:
    from constitution_utils import get_available_constitutions, get_constitution_content
except ImportError as e:
    print(f"Error importing constitution_utils in constitutions router: {e}")
    # Handle appropriately, maybe raise an error or log
    raise

router = APIRouter()

@router.get("/api/constitutions", response_model=List[ConstitutionItem])
async def get_constitutions_endpoint():
    """Returns a list of available constitutions with title and description."""
    try:
        constitutions_dict = get_available_constitutions()
        response_items = []
        for const_id, metadata in constitutions_dict.items():
            if isinstance(metadata, dict):
                response_items.append(ConstitutionItem(
                    id=const_id,
                    title=metadata.get('title', const_id.replace('_', ' ').title()),
                    description=metadata.get('description')
                ))
            else:
                logging.warning(f"Constitution '{const_id}' has unexpected data format: {metadata}. Skipping.")
        return response_items
    except Exception as e:
        logging.error(f"Error loading constitutions in endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load constitutions: {str(e)}")

@router.get("/api/constitutions/{constitution_id}/content", response_model=str)
async def get_constitution_content_endpoint(
    constitution_id: str = FastApiPath(..., title="The ID of the constitution")
):
    """Returns the raw text content of a single constitution."""
    try:
        content = get_constitution_content(constitution_id)
        if content is None:
            raise HTTPException(status_code=404, detail=f"Constitution '{constitution_id}' not found or invalid.")
        return PlainTextResponse(content=content)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error getting content for constitution {constitution_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load content for constitution '{constitution_id}'.")

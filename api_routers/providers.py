import asyncio
from typing import Dict, List

from fastapi import APIRouter

from ..model_discovery import (
    get_anthropic_models,
    get_google_genai_models,
    get_openai_models,
    get_openrouter_models,
)

router = APIRouter()

@router.get("/models", response_model=Dict[str, List[str]])
async def get_all_models() -> Dict[str, List[str]]:
    """
    Fetches available models from all supported providers concurrently.

    Returns:
        A dictionary where keys are provider names and values are lists of
        model IDs available from that provider.
    """
    # Errors are handled within each get_*_models function in model_discovery.py
    # to return an empty list, so we don't need extensive error handling here.
    results = await asyncio.gather(
        get_anthropic_models(),
        get_openai_models(),
        get_google_genai_models(),
        get_openrouter_models(),
    )

    anthropic_models, openai_models, google_genai_models, openrouter_models = results

    return {
        "anthropic": anthropic_models,
        "openai": openai_models,
        "google_genai": google_genai_models,
        "openrouter": openrouter_models,
    }
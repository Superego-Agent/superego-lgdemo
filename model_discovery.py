# Imports
import os
import json
import asyncio
from typing import List

import asyncio
import json
import os
from typing import List, Dict, Any

import anthropic
import openai
import google-genai as genai
import httpx # Using httpx for async requests instead of requests

# === Anthropic ===
async def get_anthropic_models() -> List[str]:
    """Fetches available model IDs from the Anthropic API."""
    model_ids = []
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Warning: ANTHROPIC_API_KEY environment variable not set.")
        return []
    try:
        # Client automatically uses ANTHROPIC_API_KEY env var if set
        client = anthropic.AsyncAnthropic()
        print("Fetching Anthropic Models...")
        # Use await with the async client method
        models_page = await client.models.list()
        for model_info in models_page.data:
            model_ids.append(model_info.id)
        # Note: Basic implementation, pagination not handled yet.
    except anthropic.AuthenticationError:
        print("Warning: Anthropic Authentication Error fetching models. Check ANTHROPIC_API_KEY.")
    except Exception as e:
        print(f"Warning: An error occurred fetching Anthropic models: {e}")
    return model_ids



# === OpenAI ===
async def get_openai_models() -> List[str]:
    """Fetches available model IDs from the OpenAI API."""
    model_ids = []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Warning: OPENAI_API_KEY environment variable not set.")
        return []
    try:
        # Client automatically uses OPENAI_API_KEY env var if set
        client = openai.AsyncOpenAI()
        print("Fetching OpenAI Models...")
        # Use await with the async client method
        models_list = await client.models.list()
        for model in models_list.data:
            model_ids.append(model.id)
    except openai.AuthenticationError:
        print("Warning: OpenAI Authentication Error fetching models. Check OPENAI_API_KEY.")
    except Exception as e:
        print(f"Warning: An error occurred fetching OpenAI models: {e}")
    return model_ids


# === Google Generative AI ===
async def get_google_genai_models() -> List[str]:
    """Fetches available model IDs from the Google Generative AI (Gemini) API."""
    model_ids = []
    try:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("Warning: GOOGLE_API_KEY environment variable not set for Google GenAI models.")
            return []

        # Configure implicitly uses the key for subsequent calls
        genai.configure(api_key=api_key)

        print("Fetching Google Generative AI Models (Gemini API)...")

        # genai.list_models() is synchronous. Wrap in to_thread for async context.
        try:
            # Use asyncio.to_thread to run the synchronous function in a separate thread
            model_iterator = await asyncio.to_thread(genai.list_models)
            for model in model_iterator:
                # Filter for models supporting content generation
                if 'generateContent' in model.supported_generation_methods:
                    # Return the full model name like 'models/gemini-pro'
                    model_ids.append(model.name)
        except Exception as list_models_error:
             # Catch potential errors during the sync call execution in the thread
             print(f"Warning: Error calling genai.list_models: {list_models_error}")

    except ValueError as ve:
         # Error during genai.configure
         print(f"Warning: Configuration error fetching Google GenAI models: {ve}")
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Warning: An unexpected error occurred fetching Google Generative AI models: {e}")
    return model_ids


# === OpenRouter ===
async def get_openrouter_models() -> List[str]:
    """Fetches available model IDs from the OpenRouter API."""
    model_ids = []
    api_key = os.getenv("OPENROUTER_API_KEY")
    openrouter_api_base = "https://openrouter.ai/api/v1"
    models_endpoint = f"{openrouter_api_base}/models"

    if not api_key:
        print("Warning: OPENROUTER_API_KEY environment variable not set.")
        return []

    try:
        print("Fetching OpenRouter Models...")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                models_endpoint,
                headers={"Authorization": f"Bearer {api_key}"}
            )
            # Raise HTTPStatusError for bad responses (4xx or 5xx)
            response.raise_for_status()
            models_data = response.json()

        if 'data' in models_data and isinstance(models_data['data'], list):
            for model in models_data['data']:
                if model_id := model.get('id'):
                    model_ids.append(model_id)
        else:
            print("Warning: Unexpected response format received from OpenRouter.")

    except httpx.HTTPStatusError as e:
        # More specific error message including status code and response text
        print(f"Warning: HTTP error occurred fetching OpenRouter models: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        # Catch potential network errors during the request
        print(f"Warning: An error occurred during the request to OpenRouter: {e}")
    except json.JSONDecodeError:
        print("Warning: Error decoding JSON response from OpenRouter.")
    except Exception as e:
        print(f"Warning: An unexpected error occurred fetching OpenRouter models: {e}")
    return model_ids
# Plan: Model Discovery Endpoint

This plan outlines the steps to create a backend endpoint that provides a list of available LLM models grouped by provider.

## Finalized Plan Steps:

1.  **Create New File:** `model_discovery.py` in the project root (`c:/src/superego-lgdemo/`) to house the logic for fetching model lists.
2.  **Implement Fetching Functions:**
    *   Define asynchronous functions in `model_discovery.py`:
        *   `async def get_anthropic_models() -> List[str]:`
        *   `async def get_openai_models() -> List[str]:`
        *   `async def get_google_genai_models() -> List[str]:`
        *   `async def get_openrouter_models() -> List[str]:`
    *   Adapt the verified code snippets provided previously.
    *   **Authentication:** Initially rely on environment variables (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `OPENROUTER_API_KEY`).
    *   **Return Format:** Each function returns `List[str]` (model IDs).
    *   **Error Handling:** Use `try...except` blocks, log warnings, and return `[]` on failure.
    *   **(Optional Enhancement):** Consider simple time-based caching (e.g., 5-10 minutes).
3.  **Create New API Router:** `api_routers/providers.py`.
4.  **Define API Endpoint:** `GET /api/providers/models` in `api_routers/providers.py`.
5.  **Implement Endpoint Logic:**
    *   Call the fetching functions from `model_discovery.py` concurrently (e.g., `asyncio.gather`).
    *   Aggregate results into a dictionary:
        ```json
        {
          "anthropic": ["model_id_1", ...],
          "openai": ["model_id_a", ...],
          "google_genai": ["model_id_x", ...],
          "openrouter": ["provider/model_id_p", ...]
        }
        ```
    *   Include provider keys even if the list is empty (due to errors).
6.  **Register Router:** Import the router from `api_routers.providers` and include it in `backend_server_async.py`.
7.  **Update Dependencies:** Add `requests` to `pyproject.toml` (for OpenRouter) and ensure other provider SDKs are present. Run dependency installation (`poetry lock && poetry install` or `uv` equivalent).
8.  **Documentation:** Update `memory.md` (sections `# Tech Context`, `# Progress`) to reflect the new files, endpoint, response structure, and dependencies.

## Diagrammatic Overview:

```mermaid
graph TD
    subgraph Frontend
        UI[User Interface]
    end

    subgraph Backend (FastAPI)
        A[GET /api/providers/models<br>(api_routers/providers.py)] --> B{Aggregate Results};
        B --> C[model_discovery.py];
        C --> D[get_anthropic_models()];
        C --> E[get_openai_models()];
        C --> F[get_google_genai_models()];
        C --> G[get_openrouter_models()];
    end

    subgraph External Services
        H[(Anthropic API)];
        I[(OpenAI API)];
        J[(Google GenAI API)];
        K[(OpenRouter API)];
    end

    UI -- HTTP Request --> A;
    A -- HTTP Response --> UI;

    D -- API Call --> H;
    E -- API Call --> I;
    F -- API Call --> J;
    G -- HTTP Request --> K;

    H -- Models --> D;
    I -- Models --> E;
    J -- Models --> F;
    K -- Models --> G;
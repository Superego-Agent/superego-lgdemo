# Tech Context: Superego LangGraph Agent

## 1. Backend Technologies

*   **Language:** Python (version specified in `.python-version`)
*   **Core Framework:** LangGraph (for defining and running the agent graph)
*   **LLM Integration:** LangChain (e.g., `langchain-openai`, `langchain-anthropic`) for interacting with different LLM providers.
*   **Web Server:** FastAPI, using `APIRouter` for modular endpoints (see `api_routers/`). Serves the REST API and SSE endpoint.
*   **Persistence:** LangGraph Checkpointer implementation (`AsyncSqliteSaver`) using SQLite by default (`data/sessions/conversations.db`). Checkpoints store graph state including the `configurable` dictionary.
*   **Dependency Management:** Poetry (`pyproject.toml`, `poetry.lock`).
*   **Configuration Management:**
    *   Agent instructions/constitutions: Markdown (`.md`) files.
    *   Run Configuration (`RunConfig` in `backend_models.py`): Defines runtime settings.
        *   *Current:* Contains list of `ConfiguredConstitutionModule`.
        *   *Planned:* Will include a nested `ModelConfig` object specifying LLM `provider`, `name`, and provider-specific parameters (e.g., `base_url`, `project`) via nested Pydantic models. This `ModelConfig` will be serialized and stored in the LangGraph `configurable` dictionary under the key `"model_config"`.
    *   API Keys: Securely managed via `keystore.py`. Backend logic will fetch keys based on the `provider` specified in the `RunConfig` at runtime. **API keys are NOT stored in `RunConfig` or checkpoints.**

## 2. Frontend Technologies *(Note: Developed in a separate repository)*

*   **Framework:** Svelte / SvelteKit (`svelte.config.js`, `vite.config.ts`)
*   **Language:** TypeScript (`tsconfig.json`, `.ts` files), JavaScript
*   **State Management:** `svelte/store`, `svelte-persisted-store`, `threadCacheStore`.
*   **Styling:** CSS / CSS Variables.
*   **Build Tool:** Vite (`vite.config.ts`)
*   **Package Management:** npm (`package.json`, `package-lock.json`)
*   **Utility Libraries:** `uuid`

## 3. Communication Protocol

*   **Frontend <-> Backend:** REST API for control/history, Server-Sent Events (SSE) for real-time streaming updates.

## 4. Development Environment & Setup

*   **Backend:** Requires Python environment managed by Poetry. Run via `python backend_server_async.py`.
*   **Frontend:** Requires Node.js/npm. Run development server via `npm run dev`. *(Located in separate repository)*.
*   **Database:** SQLite database file (`data/sessions/conversations.db`).
*   **API Keys:** Requires appropriate keys to be configured in `keystore.py` for desired LLM providers.

## 5. Technical Constraints & Considerations

*   **Checkpoint Alignment:** Frontend `MessageType` interface MUST align with backend checkpoint message structure.
*   **Backend API Contract:** Backend API endpoints must strictly adhere to defined request/response structures, including the `configurable` object (which will contain `"constitution_content"` and `"model_config"`).
*   **`RunConfig` Structure:** The nested `ModelConfig` structure with provider-specific parameter models must be correctly implemented and validated (`backend_models.py`).
*   **API Key Security:** Ensure `keystore.py` is handled securely and keys are not exposed elsewhere.
*   **Frontend/Backend Separation:** Requires clear API contracts and potentially separate deployment strategies. Briefing needed for frontend team.
*   **SQLite:** Default checkpointer uses SQLite; consider alternatives if high concurrency becomes an issue.
*   **CRITICAL: NO GUESSING:** Do not make assumptions about APIs (LangGraph, LangChain provider integrations), configurations, or system behavior. Verify through documentation, code examination, or asking clarifying questions.

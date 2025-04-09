# Tech Context: Superego LangGraph Agent

## 1. Backend Technologies

*   **Language:** Python (version specified in `.python-version`)
*   **Core Framework:** LangGraph (for defining and running the agent graph)
*   **Web Server:** FastAPI, using `APIRouter` for modular endpoints (see `api_routers/`). Serves the REST API and SSE endpoint.
*   **Persistence:** LangGraph Checkpointer implementation (e.g., `langgraph.checkpoint.sqlite.SqliteSaver` or `AsyncSqliteSaver` for async) using SQLite by default (as indicated by `conversations.db` files).
*   **Dependency Management:** Poetry (indicated by `pyproject.toml`, `poetry.lock`) and potentially `uv` (indicated by `uv.lock`).
*   **Configuration Files:** Markdown (`.md`) for agent instructions and constitutions.

## 2. Frontend Technologies

*   **Framework:** Svelte / SvelteKit (inferred from `svelte.config.js`, `vite.config.ts`)
*   **Language:** TypeScript (indicated by `tsconfig.json`, `.ts` files), JavaScript
*   **State Management:** `svelte/store` (for `writable`), `svelte-persisted-store` (for `uiSessions`, `knownThreadIds`). A non-persisted `historyCacheStore` (writable store holding `Record<string, HistoryEntry>`) is used for caching thread states.
*   **Styling:** Likely CSS or a preprocessor (TailwindCSS is common with SvelteKit, but not explicitly confirmed).
*   **Build Tool:** Vite (indicated by `vite.config.ts`)
*   **Package Management:** npm (indicated by `package.json`, `package-lock.json`)
*   **Utility Libraries:** `uuid` (for generating frontend session IDs)

## 3. Communication Protocol

*   **Frontend <-> Backend:** REST API for control/history, Server-Sent Events (SSE) for real-time streaming updates from agent runs.

## 4. Development Environment & Setup

*   **Backend:** Requires Python environment managed by Poetry/uv. Run via `python backend_server_async.py` (or similar).
*   **Frontend:** Requires Node.js/npm. Run development server via `npm run dev` (standard SvelteKit command). Located in `superego-frontend/` subdirectory.
*   **Database:** SQLite database file (e.g., `data/sessions/conversations.db`) used by the checkpointer.

## 5. Technical Constraints & Considerations

*   **Checkpoint Alignment:** Frontend `MessageType` interface (`global.d.ts`) MUST be kept aligned with the structure of messages stored in backend checkpoints. (Critical point from `refactor_plan.md`).
*   **Backend API Contract:** Backend API endpoints (`/api/runs/stream`, `/api/threads/...`) must strictly adhere to the request/response structures defined in `refactor_plan.md` (especially the `configurable` object).
*   **SQLite:** Default checkpointer uses SQLite, which might have limitations for high concurrency compared to other database backends (though likely sufficient for a research demo).
*   **Dependency Usage:** Use external packages where appropriate to avoid reinventing the wheel and reduce custom code complexity. The focus is on clean, minimal *custom* logic, not avoiding dependencies altogether.
*   **CRITICAL: NO GUESSING:** Do not make assumptions about APIs (especially LangGraph), configurations, or system behavior. If unsure, verify through documentation, code examination, or asking clarifying questions. Incorrect assumptions lead to bugs and unnecessary complexity.

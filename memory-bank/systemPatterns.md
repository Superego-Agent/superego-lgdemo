# System Patterns: Superego LangGraph Agent

## 1. Core Architecture (Backend)

*   **Framework:** Python application utilizing the LangGraph library, specifically `StateGraph` for defining the agent flow.
*   **Web Server:** FastAPI, serving a REST API and SSE endpoint.
*   **API Structure:** Uses FastAPI `APIRouter` for modular endpoints. The main server file includes routers and handles lifespan management.
*   **Pattern:** Multi-agent system implemented as a graph.
    *   **Entry Point:** Receives user input via API.
    *   **Input Superego Node:** The first agent to process the input. Evaluates input against a selected constitution using its LLM. Calls the `superego_decision` tool.
    *   **Conditional Edge:** Routes control based on the `allow` parameter in the `superego_decision` tool output.
        *   `allow: true`: Proceeds to the Inner Agent subgraph.
        *   `allow: false`: Terminates the flow for this input (or proceeds to a specific "blocked" state).
    *   **Inner Agent Subgraph:** A pluggable graph responsible for the main task execution. Can contain one or more nodes and edges, potentially using patterns like ReAct. Receives original input and optional `content` from the Superego.
    *   **(Future):** An Output Superego node might be added after the Inner Agent subgraph.
*   **State Management:**
    *   **Source of Truth:** LangGraph Checkpointer persists the state of the graph execution (details in `techContext.md`).
    *   **State Contents:** Includes the message history, agent working state, and the `configurable` dictionary passed during invocation.
    *   **`configurable` Metadata:** Crucial for linking frontend context to backend runs. Contains `thread_id` and `runConfig` (which includes `configuredModules` like constitutions). See `refactor_plan.md` for details.
*   **Configuration:**
    *   Agent instructions and constitutions are loaded from Markdown files (e.g., in `data/agent_instructions/`, `data/constitutions/`).
    *   The specific constitution(s) for a run are passed via the `runConfig` within the `configurable` object.

## 2. Frontend Architecture (Summary - See `refactor_plan.md` for Full Details)

*   **Framework:** Svelte single-page application.
*   **Pattern:** Thin client interacting with the backend API.
*   **State Management (See `refactor_plan.md` Section 6 for full details):**
    *   Relies on backend checkpoints as the source of truth.
    *   Uses `svelte-persisted-store` for minimal local state (`uiSessions`, `knownThreadIds`).
    *   Uses a non-persisted `activeSessionId` store to track the current UI tab.
    *   Uses a non-persisted `threadCacheStore` (Record<string, ThreadCacheData>) as an in-memory cache for fetched/streamed thread states and status.
    *   UI components subscribe to `threadCacheStore` and select data based on `threadId` props.
    *   **Service Layer:** Dedicated modules (e.g., `src/lib/services/chatService.ts`) encapsulate specific API interaction logic (like sending messages) and manage related state (like the current run configuration), keeping UI components cleaner.

## 3. Communication & Interaction
s*   **Web:**
    *   Svelte frontend communicates with the Python FastAPI backend server.
    *   **API:** RESTful endpoints for initiating runs, fetching history, and managing constitutions (details in `techContext.md`).
    *   **Streaming:** Server-Sent Events (SSE) used on the `/api/runs/stream` endpoint to push agent outputs and intermediate events (like `thread_info`) to the frontend in real-time.

## 4. Key Technical Decisions

*   **LangGraph:** Chosen for its ability to define complex agent flows and manage state.
*   **Checkpoint-Centric State:** Backend checkpointer is the single source of truth, simplifying state synchronization and enabling history/comparison features.
*   **Pluggable Inner Agent:** Allows flexibility in defining the core task-performing logic.
*   **Streaming:** Provides real-time feedback to the user.
*   **Explicit Moderation Agent:** Separates moderation concerns (Superego) from task execution (Inner Agent).
*   **FastAPI Routers:** Backend API endpoints are modularized using routers for better organization.

## 5. Coding Requirements & Guidelines

*   **CRITICAL: NO GUESSING:** Never make assumptions about APIs (especially LangGraph), configurations, library behavior, or system state. Verify through documentation, code examination, or asking clarifying questions. Incorrect assumptions are a primary source of bugs and complexity in this project. (Mistake Tally: 2 - Incorrect Pydantic Union validation)
*   **Refactoring Order:** When refactoring across layers (e.g., backend API, frontend API client, frontend UI), prioritize verifying/implementing the lower layers first (Backend -> Frontend API Client -> Frontend UI). Avoid refactoring UI components based on unverified API contracts. (Mistake Tally: 1)
*   **Simplicity & Focus (Custom Code):** Prioritize direct, functional custom code. Avoid unnecessary complexity, deep nesting, or premature optimization *in the code you write*. Focus on the core research demo functionality.
*   **Leverage Dependencies:** Use external packages effectively to avoid reinventing the wheel. The goal is minimal *custom* code, not minimal dependencies.
*   **Svelte Reactivity & Declarative Code:** Frontend code, especially within `.svelte` files, MUST be declarative. Leverage Svelte's reactivity system (stores, derived stores, reactive declarations `$:`) wherever possible. Avoid manual state management or imperative DOM manipulation if a reactive/declarative approach exists.
*   **Extensibility:** Structure code to accommodate future features (output superego, more inner agents) cleanly.
*   **Lightweight Custom Code:** Avoid heavy boilerplate or overly defensive error handling *in custom logic* where it's not essential for the demo's purpose. Rely on library defaults where sensible.
*   **Abstractions (Custom Code):** Use elegant abstractions *within custom code* where appropriate to avoid repeating complex patterns or logic. (Per user request).
*   **Commenting Policy (Strict):**
    *   Comments are **ONLY** for permanent, essential clarification of non-obvious logic that cannot be improved via naming/structure. Aim for self-documenting code first.
    *   **NO** ephemeral comments (e.g., `// TODO: fix this later`). Do not use placeholders for missing functionality; leave it clearly broken until dependencies are met. (Mistake Tally: 40)
    *   **NO** comments explaining the obvious or narrating simple code (e.g., "Type X comes from global.d.ts"). (Mistake Tally: 1)
    *   **Svelte Template Comments:** Within the HTML template part of `.svelte` files, use ONLY HTML-style comments (`<!-- comment -->`). Do NOT use JavaScript-style comments inside template expressions (`{/* INCORRECT */}`). Standard JavaScript comments (`//`, `/* */`) are acceptable within `<script>` tags.
    *   Adding comments requires justification.
*   **Global Types:** Do not add comments stating that types from `global.d.ts` are global; this is assumed project knowledge. Do not explicitly import types from `global.d.ts`. (Mistake Tally: 1)
*   **Tool Usage:** Use tools correctly, paying attention to syntax, escaping rules (e.g., for `apply_diff`), and avoiding inclusion of tool-specific markers (like `<![CDATA[...]]>`) in file content. (Mistake Tally: 3 - `apply_diff` escaping/parsing; `write_to_file` CDATA inclusion; `apply_diff` content mismatch)

# Memory Bank: Superego LangGraph Agent

---
# Project Brief
---

## 1. Core Goal

Develop a multi-agent system using LangGraph featuring a "Superego" agent for input moderation based on configurable constitutions, gating interaction with a primary "Inner Agent".

## 2. Project Evolution

*   Initial Phase (CLI - Historical): Demonstrated core Superego -> Inner Agent flow via a command-line interface.
*   Current Phase (Svelte Frontend):
    *   Developed a Svelte frontend interacting with the LangGraph backend via REST API and SSE for streaming.
    *   Leverages LangGraph checkpoints as the source of truth for conversation state.
    *   Implemented robust frontend state management (`threadCacheStore`).
    *   Focus now shifts to UI polish, code cleanup, and feature enhancements.

## 3. Future Roadmap (High-Level)

1.  UI Polish & Minor Fixes: Address small bugs and improve user experience.
2.  Code Cleanup & Refactoring: Improve code quality (e.g., Sass, abstractions, utils).
3.  Config Card Enhancements: Add rename, delete, enable/disable toggle, and constitution display.
4.  User API Key: Allow users to provide their own API keys.
5.  Model/Provider Selection: Enable switching LLM models and providers (e.g., OpenAI, Google).
6.  (Longer Term): Output Superego, advanced comparison modes, etc.

## 4. Key Principles

*   Modularity: Support interchangeable constitutions and inner agents.
*   Extensibility: Design for future feature additions.
*   Checkpoint-Centric: Backend checkpointer is the single source of truth.
*   Thin Client: Frontend derives state primarily from backend data.
*   Clean Code: Prioritize clarity, conciseness, and well-structured code. Avoid unnecessary complexity.
*   (See `# System Patterns` and `# Active Context` sections below for detailed development guidelines and current focus).

## 5. Target Audience

*   Researchers/Developers exploring AI safety, constitutional AI, and multi-agent systems.
*   Users investigating the impact of moderation rules on agent behavior.

---
# Product Context
---

## 1. Problem / Motivation

*   Research Platform: Provide a transparent platform for researching Constitutional AI concepts, specifically input moderation via a "Superego" agent within a LangGraph system.
*   Investigating Moderation: Enable users to study how different constitutions affect agent behavior and interaction flow.
*   Extensible Framework: Serve as a base for future research (e.g., output screening, varied inner agents).

## 2. Solution Overview

A multi-agent system using LangGraph, accessible via a Svelte frontend:
*   Input Superego: Moderates user input against a selected constitution using the `superego_decision` tool to gate access to the Inner Agent.
*   Inner Agent: Pluggable subgraph executing the main task.
*   Frontend Interaction: Users interact via the Svelte UI, managing configurations and observing streamed results.
*   State Management: LangGraph checkpoints are the backend source of truth, reflected in the frontend's `threadCacheStore`.

## 3. User Experience Goals

*   Transparency: Allow clear observation of the Superego's decision-making and the impact of constitutions.
*   Experimentation: Facilitate easy selection and comparison of different run configurations (constitutions, models, etc.).
*   Clear Feedback: Provide real-time streaming output and clear indication of the agent flow.

## 4. Core Functionality & Future Enhancements

Current User Flow:
1.  Setup: User selects/configures run parameters (constitutions) via the UI.
2.  Input: User submits a prompt through the chat interface.
3.  Moderation & Execution: Backend Superego moderates; if allowed, Inner Agent executes. Results are streamed to the UI.
4.  Observation: User observes the outcome in the context of the chosen configuration.

Planned Enhancements (See Roadmap in `# Project Brief` section):
*   Config Management: Enhanced UI for renaming, deleting, enabling/disabling configurations. Display configured constitutions on cards.
*   Flexibility: Allow users to provide their own API keys and select different LLM models/providers.
*   Polish: General UI improvements and minor fixes.
*   Code Quality: Refactoring for better structure and maintainability (Sass, utils).

---
# System Patterns
---

## 1. Backend Architecture

*   Framework: Python application using LangGraph (`StateGraph`) for agent flow.
*   Web Server: FastAPI serving a REST API and SSE endpoint, using `APIRouter` for modularity.
*   Core Pattern: Multi-agent graph (Input Superego -> Conditional Edge -> Inner Agent Subgraph).
    *   Superego uses `superego_decision` tool (`allow: boolean`, `content: string`) to control flow based on constitution checks.
    *   Inner Agent is a pluggable subgraph for task execution.
*   State Management: LangGraph Checkpointer (SQLite default) is the source of truth. State includes messages and `configurable` metadata (`thread_id`, `runConfig`).
    *   Key: Backend accepts `thread_id` in `configurable`, allowing frontend to pre-define it.
*   Configuration: Constitutions loaded from Markdown files, specified via `runConfig` in `configurable`.

## 2. Frontend Architecture

*   Framework: Svelte single-page application (SPA).
*   Pattern: Thin client interacting with the backend API.
*   State Management:
    *   Relies on backend checkpoints as the source of truth for conversation history.
    *   `svelte-persisted-store`: Manages minimal persistent UI state (`uiSessions`, `knownThreadIds`).
    *   `svelte/store`: Manages transient UI state (`activeSessionId`, `threadCacheStore`).
    *   `threadCacheStore`: `Writable<Record<string, ThreadCacheData>>`. In-memory cache holding the frontend's view of each thread's state (`history`, `isStreaming`, `error`). UI components derive state from this store based on `threadId`.
    *   Service Layer: Modules (e.g., `chatService.ts`) encapsulate API logic and related state management (e.g., constitution selection).

## 3. Communication

*   Frontend <-> Backend:
    *   REST API: For fetching history, managing constitutions, etc.
    *   SSE: `/api/runs/stream` endpoint pushes real-time agent outputs and state updates (`run_start`, `chunk`, `tool_result`, `end`, `error`). `isStreaming` flag in `threadCacheStore` is managed via `run_start` and `end`/`error` events.

## 4. Key Technical Decisions

*   LangGraph: Enables complex agent flows and state management.
*   Checkpoint-Centric State: Backend checkpointer is the single source of truth.
*   Streaming (SSE): Provides real-time feedback.
*   Explicit Moderation Agent: Separates moderation (Superego) from task execution (Inner Agent).

## 5. Coding Requirements & Guidelines (CRITICAL)

*   A. NO GUESSING / ASSUMPTIONS:
    *   NEVER assume API behavior (esp. LangGraph), library features, configurations, or system state.
    *   ALWAYS verify through documentation, code examination, or asking clarifying questions *before* implementing. Incorrect assumptions are a primary source of bugs. (Example Anti-Pattern: Assuming LangGraph dictates `thread_id` generation).
*   B. Careful, Iterative Development:
    *   Work step-by-step. Confirm understanding and verify intermediate steps.
    *   Avoid "text-walling" large blocks of code or explanation. Prefer focused, incremental changes.
    *   Do not rush ahead based on incomplete information.
*   C. Declarative Svelte:
    *   Leverage Svelte's reactivity (`$:` , derived stores) wherever possible.
    *   Avoid unnecessary local state variables; derive state from stores when feasible.
    *   Minimize imperative logic in components.
*   D. Strict Commenting Policy:
    *   Comments are ONLY for essential clarification of non-obvious logic *after* attempting self-documenting code.
    *   NO narrative, obvious, or ephemeral (`// TODO`) comments.
    *   NO placeholders for missing functionality; implement or leave clearly broken.
    *   Use HTML comments (`<!-- -->`) in Svelte templates, JS comments (`//`, `/* */`) in `<script>`.
*   E. Clean Code & Abstraction:
    *   Prioritize clear, concise, functional custom code.
    *   Use abstractions (utility functions, services, potentially SASS mixins later) to avoid repetition and improve structure. Move reusable logic out of components (e.g., into `utils.ts` or service files).
    *   Refactor monolithic components as needed.
*   F. Tool Usage:
    *   Use tools correctly (syntax, escaping). Re-read files if `apply_diff` fails unexpectedly.

## 6. Key Learnings / Anti-Patterns to Avoid

*   Verification First: Verify backend/API contracts *before* implementing dependent frontend logic.
*   State Management: Keep state management lean. Use `threadCacheStore` as the primary source for thread view state. Avoid mixing backend state concepts with purely transient UI flags directly within backend data structures (use wrappers like `ThreadCacheData`).
*   Global Types: Types in `global.d.ts` are globally available; do not import them.
*   Plan Adherence: Strictly follow agreed-upon plans. Do not introduce unapproved elements.
*   Component Responsibility: Keep UI components focused on their specific task (display vs. container logic).

---
# Tech Context
---

## 1. Backend Technologies

*   Language: Python (version specified in `.python-version`)
*   Core Framework: LangGraph (for defining and running the agent graph)
*   Web Server: FastAPI, using `APIRouter` for modular endpoints (see `api_routers/`). Serves the REST API and SSE endpoint.
*   Persistence: LangGraph Checkpointer implementation (e.g., `AsyncSqliteSaver`) using SQLite by default.
*   Dependency Management: Poetry (`pyproject.toml`, `poetry.lock`) and potentially `uv` (`uv.lock`).
*   Configuration Files: Markdown (`.md`) for agent instructions and constitutions.

## 2. Frontend Technologies

*   Framework: Svelte / SvelteKit (`svelte.config.js`, `vite.config.ts`)
*   Language: TypeScript (`tsconfig.json`, `.ts` files), JavaScript
*   State Management: `svelte/store`, `svelte-persisted-store` (`uiSessions`, `knownThreadIds`). Non-persisted `threadCacheStore` (`Writable<Record<string, ThreadCacheData>>`) for thread view state. Service modules (`chatService.ts`) manage related state.
*   Styling: CSS (potentially migrating to Sass).
*   Build Tool: Vite (`vite.config.ts`)
*   Package Management: npm (`package.json`, `package-lock.json`)
*   Utility Libraries: `uuid` (frontend session IDs)

## 3. Communication Protocol

*   Frontend <-> Backend: REST API (control/history), SSE (real-time streaming via `/api/runs/stream`).

## 4. Development Environment & Setup

*   Backend: Python environment (Poetry/uv). Run via `python backend_server_async.py`.
*   Frontend: Node.js/npm. Run via `npm run dev` in `superego-frontend/`.
*   Database: SQLite file (e.g., `data/sessions/conversations.db`) for checkpointer.

## 5. Technical Constraints & Considerations

*   Checkpoint Alignment: Frontend `MessageType` (`global.d.ts`) must align with backend checkpoint message structure.
*   Backend API Contract: Adhere strictly to defined request/response structures (esp. `configurable` object).
*   SQLite: Default checkpointer has potential concurrency limits (acceptable for demo).
*   Dependency Usage: Leverage external packages; focus on minimal *custom* code.
*   CRITICAL: NO GUESSING: Verify assumptions about APIs, configs, behavior. Ask or check code/docs.

---
# Active Context (As of 2025-04-11 ~11:01 AM)
---

## 1. Current Status & Focus

*   Frontend State Refactor: COMPLETE. The architecture based on `threadCacheStore` is implemented.
*   Backend History Fix: COMPLETE. `nodeId` is correctly handled.
*   ChatView Spinner Fix: COMPLETE. Spinner now only shows during active streaming.
*   Current Focus: Transitioning from refactoring/bugfixing to the new roadmap: UI polish, code cleanup, and feature implementation.

## 2. Immediate Next Steps (Roadmap Phase 1 & 2)

1.  UI Polish & Minor Fixes: Address outstanding minor UI issues as specified by the user. (Details TBD).
2.  Code Cleanup & Refactoring:
    *   Update `requirements.txt` (if needed).
    *   Improve code quality (e.g., investigate Sass migration, add abstractions/utils).
    *   Refactor components for better structure and reusability.

## 3. Upcoming Roadmap Items (High-Level)

*   Config Card Enhancements (Rename, Delete, Toggle, Constitution Display).
*   User API Key Feature.
*   Model/Provider Selection Feature.
*   (See `# Project Brief` section for full roadmap).

## 4. Key Guiding Principles & Learnings (Consolidated)

*   A. Verify, Don't Assume: ALWAYS verify assumptions about APIs (esp. LangGraph - e.g., `thread_id` handling), libraries, configs, state. Check docs/code or ask. (Mistake Tally: ~7)
*   B. Iterate Carefully: Work step-by-step. Confirm understanding. Avoid large, unverified changes. (Mistake Tally: ~3)
*   C. Use Svelte Reactivity: Leverage `$:` and derived stores. Avoid unnecessary local state. (Mistake Tally: ~2)
*   D. Strict Commenting: ONLY essential comments for non-obvious logic. NO narrative, TODOs, placeholders, or obvious explanations. (Mistake Tally: ~41)
*   E. Clean Code: Prioritize clarity, conciseness. Use abstractions/utils. Refactor monolithic components. (Mistake Tally: ~2)
*   F. Correct Tool Usage: Use tools precisely (syntax, escaping). Re-read files on `apply_diff` errors. (Mistake Tally: ~12)
*   G. State Management: Keep state lean. Use `threadCacheStore` for thread view state. Use wrappers (`ThreadCacheData`) to combine backend/frontend state cleanly. (Mistake Tally: ~3)
*   H. Follow Plans & Instructions: Adhere to agreed plans. Confirm understanding before acting. (Mistake Tally: ~3)
*   I. Other: Check global types (`global.d.ts`), component props/types, backend imports, Pydantic validation, mode restrictions, server caching effects. (Mistake Tally: ~12)

*(Mistake tallies are approximate aggregates from previous context)*

---
# Progress (As of 2025-04-11 ~11:02 AM)
---

## 1. Completed Milestones

*   Core Backend Concept (CLI - Historical).
*   Svelte Frontend Foundation & API Integration (REST/SSE).
*   Checkpoint-Centric State Management (Backend & Frontend `threadCacheStore`).
*   Constitution Handling (Selection & API).
*   Backend History `nodeId` Fix.
*   Various UI Fixes (Dark mode, scrolling, message cards, etc.).
*   ChatView Spinner Logic Fix.

## 2. Current Phase: Polish, Cleanup & Feature Development

*   **Immediate Focus:**
    1.  UI Polish & Minor Fixes (Details TBD by user).
    2.  Code Cleanup & Refactoring (Update requirements, investigate Sass, abstractions/utils).
*   **Next Major Features:**
    *   Config Card Enhancements (Rename, Delete, Toggle, Constitution Display).
    *   User API Key Input.
    *   Model/Provider Selection.

## 3. Known Issues / Risks

*   LangGraph API Complexity: Requires careful verification when used.
*   Stream Processing Logic (`streamProcessor.ts`): Core logic, needs testing if modified.
*   Minimal Error Handling: Current focus is on core functionality (Acceptable for demo).

## 4. Key Decision Evolution Summary

*   Shifted to Checkpoint-Centric State (Backend source of truth).
*   Adopted `threadCacheStore` with `ThreadCacheData` for frontend state view.
*   Formalized coding standards & iterative development process (See `# System Patterns` section).
*   Refined constitution handling (global store, service layer).
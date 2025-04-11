# Memory Bank: Superego LangGraph Agent

---
# Project Brief
---

## 1. Core Goal

Develop a multi-agent system using LangGraph featuring a "Superego" agent for input moderation based on configurable constitutions, gating interaction with a primary "Inner Agent".

## 2. Project Evolution

*   Current Phase (Svelte Frontend):
    *   Developed a Svelte frontend interacting with the LangGraph backend via REST API and SSE for streaming.
    *   Leverages LangGraph checkpoints as the source of truth for conversation state.
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
*   Note that it is a RESEARCH DEMO - extensive error handling, etc. for a production environment is not desirable. It should fail fast and loud. 

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
*   State Management (Evolving Pattern - Refactoring in Progress):
    *   Relies on backend checkpoints as the source of truth for conversation history.
    *   **Target Pattern (Rune-based):** Utilize Svelte 5 Runes (`$state`, `$derived`, `$effect`) within **classes** defined in `.svelte.ts` files, typically located in `src/lib/state/`. Export instances of these classes (e.g., `appState` from `state/app.svelte.ts`, `uiState` from `state/ui.svelte.ts`). State properties and mutation methods are accessed via these instances.
    *   **Persistence:** Use the `persistedLocalState` utility (`src/lib/utils/persistedLocalState.svelte.ts`) to wrap exported state class instances requiring `localStorage` persistence (e.g., `sessionState`).
    *   **API Logic:** Encapsulate API interactions (REST, SSE) in dedicated modules within `src/lib/api/` (e.g., `api/sse.svelte.ts`, `api/rest.svelte.ts`). State classes may call functions from these API modules.
    *   **(Legacy Pattern):** Older parts of the codebase might still use `svelte/store` (`writable`) or `svelte-persisted-store`. These are being phased out. `threadCacheStore` (now part of `appState`) holds thread view state.

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
*   D. Effective Commenting Policy (STRICTLY ENFORCED):
    *   **Goal:** Improve code clarity and long-term maintainability through *thoughtful* commenting. This policy is strictly enforced regarding the *quality and purpose* of comments, not their mere presence. Comments are encouraged where they add value but avoided otherwise.
    *   **Prioritize Self-Documenting Code:** Write clear, well-named code that minimizes the *need* for comments.
    *   **Approved Uses (Add Comments Respectfully):**
        *   Essential clarification of complex or non-obvious logic/algorithms.
        *   Explaining the "why" behind a specific implementation choice if it's not immediately clear from the code.
        *   Section headings (`// --- Section Name ---`) in scripts to delineate logical blocks.
        *   Template structure guides (`<!-- === Section Name === -->`) in Svelte markup to improve readability.
    *   **Strictly Prohibited:**
        *   Narrative comments that just describe *what* the code does (e.g., `// loop through items`). The code should say *what*.
        *   Obvious comments stating the trivial (e.g., `// increment counter`).
        *   Ephemeral comments like `// TODO`, `// FIXME` (use issue tracking instead).
        *   Commented-out code (use version control).
        *   Placeholders for missing functionality (implement or remove).
    *   **Formatting:** Use HTML comments (`<!-- -->`) in Svelte templates, JS comments (`//`, `/* */`) in `<script>`.
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

## 4. Technical Constraints & Considerations

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
*   **Svelte 5 Migration:** Automated migration tool run (2025-04-11). Components now use Svelte 5 syntax (`$props`, etc.). Note: The migration might require cleanup.
*   **Immediate Focus:** **Execute Rune Refactoring & Structure Standardization.** Implement the phased plan documented in `rune_refactor_implementation_plan.md`. This involves migrating state to the class-based Rune pattern and organizing files into `src/lib/state/` and `src/lib/api/`.
*   **Current Step:** Delegating Phase 0 & 1 (Prepare Dirs, Refactor Stream State & SSE API) to the Code agent.

## 2. Current Task: Execute Rune Refactoring & Structure Standardization

**Goal:** Implement the phased plan defined in `rune_refactor_implementation_plan.md`. This involves migrating state management to Svelte 5 Runes using the established class-based pattern and reorganizing files into dedicated `src/lib/state/` and `src/lib/api/` directories.

**Method:** Delegate implementation phase by phase to the Code agent, providing specific instructions and context for each phase based on the plan.

**Current Phase Delegation:** Phase 0 & 1 (Prepare Dirs, Refactor Stream State & SSE API).
## 3. Upcoming Roadmap Items (High-Level)

*   Config Card Enhancements (Rename, Delete, Toggle, Constitution Display).
*   User API Key Feature.
*   Model/Provider Selection Feature.
*   (See `# Project Brief` section for full roadmap).

## 4. Key Guiding Principles & Learnings (Consolidated)

*   **A. Context Conservation (CRITICAL):** LLM performance degrades significantly with excessive context length. Every token included in prompts, code, memory, and chat history impacts focus, accuracy, and cost. Therefore:
    *   **Be Concise:** Keep plans, summaries, and memory entries focused and concise, but ensure *necessary* detail and nuance are captured. Balance brevity with clarity.
    *   **Avoid Redundancy in Chat:** Do NOT include code snippets, diffs, or lengthy file contents in chat responses if they can be accessed or applied via tools. Use tools directly. The user can review tool inputs/outputs separately. This is a major source of context waste.
    *   **Targeted Tool Use:** When requesting information (e.g., `read_file`), request only the necessary portions (using line numbers) rather than entire files whenever feasible.
    *   **Purpose:** This discipline saves tokens, improves model focus, reduces costs, and leads to better overall agent performance and more successful task completion.
*   **B. Verify, Don't Assume:** ALWAYS verify assumptions about APIs (esp. LangGraph - e.g., `thread_id` handling), libraries, configs, state. Check docs/code or ask. Meticulously address *all* feedback/errors (TS errors, tool failures, user corrections). Don't fix comments instead of code. Verify imports and syntax. (Mistake Tally: ~7 + recent detail errors)
*   **C. Iterate Carefully:** Work step-by-step. Confirm understanding. Avoid large, unverified changes. (Mistake Tally: ~3)
*   **D. Svelte 5 Mastery:** Deep understanding of Runes (`$state`, `$derived`, `$effect`), their reactivity, and correct usage (esp. `$derived` access) is crucial. Consult migration guide (`SVELTE-V5-MIGRATION-GUIDE.md`) and docs. Avoid Svelte 4 patterns ($:, store syntax) unless interfacing with legacy stores (`get()`). (Mistake Tally: ~2 + recent Rune errors)
*   **E. Effective Commenting (Strictly Enforced):** Comments must add value (clarify non-obvious logic/why, provide structure). Avoid obvious/narrative/TODOs/placeholders/commented-code. Quality over quantity. **Strict adherence required.** (Mistake Tally: ~46 + recent violations)
*   **F. Clean Code & Abstraction:** Prioritize simple, direct, concise code. Aggressively refactor repeated logic into helpers (DRY). Remove verbose logging/checks. Use abstractions/utils. Refactor monolithic components. (Mistake Tally: ~2 + recent DRY issues)
*   **G. Correct Tool Usage & Adherence:** Use tools precisely (syntax, escaping). Re-read files on `apply_diff` errors. Strict adherence to tool usage rules (e.g., `ask_followup_question` when needed) is mandatory. (Mistake Tally: ~12 + recent violations)
*   **H. State Management:** Keep state lean. Use wrappers (`ThreadCacheData`) to combine backend/frontend state cleanly. (Mistake Tally: ~3)
*   **I. Follow Plans & Instructions:** Define full task scope (incl. refactoring consumers) before implementation. Plan complex changes methodically (Architect mode). Adhere to agreed plans. Confirm understanding before acting. **Stay focused on the core task objective.** (Mistake Tally: ~5 + recent scope/focus issues)
*   **J. Other:** Check global types (`global.d.ts`), component props/types, backend imports, Pydantic validation, mode restrictions, server caching effects. (Mistake Tally: ~12)
*   **K. Adapt to Feedback:** Refine policies (like commenting) and approaches based on user feedback and evolving requirements. (Mistake Tally: ~1)

*   **L. Narrative Commenting:** Avoided narrative/obvious comments. (Rule 3.8 / System Pattern 5.D / Active Context E) (Mistake Tally: 46)
*   **M. Global Type Imports:** Avoided importing types already globally defined in `global.d.ts`. (Superego Rule 2.2 / System Pattern 6.B / Active Context J) (Mistake Tally: 12)
*   **N. LOP Adherence:** MUST actually perform LOP logging actions (e.g., memory updates), not simulate them. (Memory Rule 5 / LOP Step 2 / Active Context G) (Mistake Tally: 1)

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
*   Refactor: Separated SSE stream logic from `api.ts` into `sseService.ts`.
*   Refactor: Extracted pagination logic from `ChatInterface.svelte` into `Paginator.svelte`.
## 2. Current Phase: Code Reorganisation (Context Minimisation)

*   **Current Focus:** Applying **Method 1 (Code Structure & Patterns)** to the frontend codebase (`superego-frontend/src/`).
*   **Next Steps (Post-Reorganisation):** Resume roadmap features like Config Card Enhancements, User API Key, Model Selection, etc. (See `# Project Brief` section).
## 3. Known Issues / Risks

*   LangGraph API Complexity: Requires careful verification when used.
*   Stream Processing Logic (`streamProcessor.ts`): Core logic, needs testing if modified.
*   Minimal Error Handling: Current focus is on core functionality (Acceptable for demo).

## 4. Key Decision Evolution Summary

*   Shifted to Checkpoint-Centric State (Backend source of truth).
*   Adopted `threadCacheStore` with `ThreadCacheData` for frontend state view.
*   Formalized coding standards & iterative development process (See `# System Patterns` section).
*   Refined constitution handling (global store, service layer).

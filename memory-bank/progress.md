# Progress: Superego LangGraph Agent (As of 2025-04-28 ~02:57 PM)

## 1. What Works / Completed

*   **Core Backend Concept (CLI):** Initial CLI version exists.
*   **Basic Moderation:** Superego agent concept exists.
*   **Pluggable Inner Agent:** Architecture supports this.
*   **Frontend Foundation:** SvelteKit project setup exists.
*   **Frontend State Refactor (COMPLETED):**
    *   Implemented new state architecture (`refactor_plan.md`).
    *   Refactored stores, API layer, stream processor, UI components (`ChatView`, `ChatInterface`).
*   **Constitution Handling & Sending Logic Refactor (COMPLETED):**
    *   Implemented global store and service layer (`chatService.ts`).
    *   Integrated constitution selection and API sending logic.
*   **Backend API:** Verified constitution endpoints.
*   **Plan Documentation:** Updated `refactor_plan.md`, `activeContext.md`, and `progress.md`.
*   **Various Frontend Fixes:** Addressed `svelte-check` errors, updated `MessageCard` props, integrated global constitution loading.
*   **Backend History `nodeId` Fix (COMPLETED):**
    *   Ensured `inner_agent` sets `msg.name`.
    *   Refactored history endpoints (`api_routers/threads.py`) to use `StateSnapshot` and correctly derive `nodeId` from `msg.name`.
    *   Fixed related import and validation errors.

## 2. What's Left / In Progress

*   **Feature: Model Switcher (In Progress)**
    *   **Overall Goal:** Integrate model switcher via `RunConfig`.
    *   **Phase 1: Backend Config & Storage (Next Action)**
        *   **Step 1:** Refine `backend_models.py`: Define nested `ModelConfig` within `RunConfig` using provider-specific parameter models (e.g., `OpenAIParams`) and a validator. No API key info in `RunConfig`.
        *   **Step 2:** Update `api_routers/runs.py`: Modify `/api/runs/stream` to accept the new `RunConfig`, serialize `ModelConfig`, and store it under `"model_config"` in the LangGraph `configurable` dictionary (persisted in checkpoints).
    *   **Phase 2: Backend LLM Logic (Planned)**
        *   **Step 3:** Update `superego_core_async.py`: Implement LLM switching logic to read `"model_config"`, fetch API keys from `keystore.py` based on provider, instantiate the correct LangChain client with appropriate parameters, and invoke it.
    *   **Phase 3: Future Work (Planned)**
        *   **Step 4:** Output Handling: Defer handling provider-specific output metadata and detailed "thinking" steps. Focus on core text response initially.
        *   **Step 5:** Frontend Integration: Prepare a briefing for the separate frontend team after backend work. *(Note: Frontend is in a separate repository)*.
    *   **Key Decisions:**
        *   Use provider-specific Pydantic models for parameters.
        *   API keys managed via `keystore.py` based on provider, not stored in `RunConfig`.
        *   Frontend is separate, requires briefing.

*   **Small Cleanups (Planned):** Address minor code improvements/issues (Details TBD by user).
*   **Implement Comparison Mode (Planned):** Develop side-by-side run comparison feature (Details TBD by user).
*   **Testing:** Thoroughly test the refactored workflows and recent fixes.
*   **Configuration CRUD (Future):** UI/API for managing constitutions.
*   **Output Superego (Future):** Implement output screening agent.
*   **Inner Agent Variety (Future):** Add more inner agent options.

## 3. Known Issues / Risks

*   **Complexity of LangGraph API:** Requires careful verification.
*   **Complexity of Stream Processing:** Logic in `streamProcessor.ts` needs careful review/testing.
*   **Old `localStorage` Data:** Will be discarded. (Acceptable).
*   **Minimal Error Handling:** Focus on core demo functionality. (Acceptable).
*   **Frontend/Backend Split:** Requires clear communication and briefing for frontend integration.

## 4. Decision Evolution

*   **Shift to Checkpoint-Centric State:** Decision remains firm.
*   **Formalized Coding Standards & Refactoring Order:** Explicit guidelines added/refined. Order adjusted to API -> Transformation -> UI.
*   **Tool Naming:** Corrected Superego tool name to `superego_decision`.
*   **Focus on Research Transparency:** User experience goals remain focused on observability.
*   **Backend API Structure:** Confirmed use of FastAPI routers.
*   **State Management Refinement:** Adopted `threadCacheStore` with `ThreadCacheData`.
*   **Constitution Handling:** Shifted from component-level fetch to global store (`globalConstitutionsStore`). Refactored sending logic into `chatService.ts`.
*   **Model Configuration (`RunConfig`):** Decided on nested `ModelConfig` with provider-specific parameter models, validation, and separate API key handling via `keystore.py`.

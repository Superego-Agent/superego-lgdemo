# Progress: Superego LangGraph Agent (As of 2025-04-29 ~03:15 PM)

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
*   **Feature: Model Switcher (COMPLETED - Backend)**
    *   **Overall Goal:** Integrate model switcher via `RunConfig`.
    *   **Phase 1: Backend Config & Storage (DONE)**
        *   **Step 1:** Refined `backend_models.py`: Defined nested `ModelConfig` within `RunConfig` using provider-specific parameter models and a validator. No API key info in `RunConfig`.
        *   **Step 2:** Updated `api_routers/runs.py`: Modified `/api/runs/stream` to accept the new `RunConfig`, serialize `ModelConfig`, and store it under `"model_config"` in the LangGraph `configurable` dictionary.
    *   **Phase 2: Backend LLM Logic (DONE)**
        *   **Step 3:** Updated `superego_core_async.py`: Implemented LLM switching logic to read `"model_config"`, fetch API keys from `keystore.py`, instantiate the correct LangChain client with strict error handling.
    *   **Phase 3: Future Work / Frontend**
        *   **Step 4:** Output Handling: Handling provider-specific output metadata and detailed "thinking" steps remains deferred.
        *   **Step 5:** Frontend Integration: Frontend briefing created (`memory-bank/frontend_briefing_model_switcher.md`). Awaiting frontend implementation. *(Note: Frontend is in a separate repository)*.
    *   **Key Decisions:**
        *   Use provider-specific Pydantic models for parameters.
        *   API keys managed via `keystore.py` based on provider, not stored in `RunConfig`.
        *   Frontend is separate, requires briefing.

## 2. What's Left / In Progress

*   **Frontend Implementation: Model Switcher (Next Action - External)**: Implement UI changes based on `frontend_briefing_model_switcher.md` in the separate frontend repository.
*   **Small Cleanups (Planned):** Address minor code improvements/issues (Details TBD by user).
*   **Implement Comparison Mode (Planned):** Develop side-by-side run comparison feature (Details TBD by user).
*   **Testing:** Thoroughly test the refactored workflows and recent fixes, including model switching once frontend is ready.
*   **Configuration CRUD (Future):** UI/API for managing constitutions.
*   **Output Superego (Future):** Implement output screening agent.
*   **Inner Agent Variety (Future):** Add more inner agent options.

## 3. Known Issues / Risks

*   **Complexity of LangGraph API:** Requires careful verification.
*   **Complexity of Stream Processing:** Logic in `streamProcessor.ts` needs careful review/testing.
*   **Old `localStorage` Data:** Will be discarded. (Acceptable).
*   **Minimal Error Handling:** Focus on core demo functionality. (Acceptable).
*   **Frontend/Backend Split:** Requires clear communication and briefing for frontend integration. Model switcher integration depends on external frontend work.

## 4. Decision Evolution

*   **Shift to Checkpoint-Centric State:** Decision remains firm.
*   **Formalized Coding Standards & Refactoring Order:** Explicit guidelines added/refined. Order adjusted to API -> Transformation -> UI.
*   **Tool Naming:** Corrected Superego tool name to `superego_decision`.
*   **Focus on Research Transparency:** User experience goals remain focused on observability.
*   **Backend API Structure:** Confirmed use of FastAPI routers.
*   **State Management Refinement:** Adopted `threadCacheStore` with `ThreadCacheData`.
*   **Constitution Handling:** Shifted from component-level fetch to global store (`globalConstitutionsStore`). Refactored sending logic into `chatService.ts`.
*   **Model Configuration (`RunConfig`):** Decided on nested `ModelConfig` with provider-specific parameter models, validation, and separate API key handling via `keystore.py`. (Implementation Complete).

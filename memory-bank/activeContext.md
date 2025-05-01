# Active Context: Superego LangGraph Agent (As of 2025-04-29 ~03:15 PM)

## 1. Current Major Focus: Feature - Model Switcher (Backend Complete)

*   **Goal:** Implement backend support for selecting different LLM providers and models via the `RunConfig`.
*   **Status:** **COMPLETED**. Backend models, API endpoint, and core graph logic updated. Frontend briefing created.

## 2. Recent Changes (During Current Session)

*   **Model Switcher Planning:**
    *   Investigated current `RunConfig` storage.
    *   Investigated configuration requirements for various LLM providers.
    *   Defined V2 `RunConfig` structure (nested `ModelConfig`, provider-specific params, validation, no API key reference).
    *   Confirmed API key handling via `keystore.py`.
    *   Investigated LangGraph's "thinking" step handling (deferred).
    *   Acknowledged separate frontend repository.
    *   Finalized multi-phase implementation plan.
*   **Model Switcher Implementation (Backend):**
    *   **Phase 1 (DONE):** Updated `backend_models.py` with `ModelConfig` and provider params; updated `/api/runs/stream` in `api_routers/runs.py` to store `"model_config"` in checkpoint `configurable`.
    *   **Phase 2 (DONE):** Updated `superego_core_async.py` to dynamically instantiate LLM clients based on `"model_config"`, fetch keys from `keystore.py`, and implement strict error handling for invalid/missing config or keys.
*   **Frontend Briefing:** Created `memory-bank/frontend_briefing_model_switcher.md` detailing API changes and UI requirements for the frontend team.
*   **Memory File Updates:** Updated `progress.md`, `activeContext.md`, `productContext.md`, `techContext.md` to reflect current status.

## 3. Immediate Next Steps

1.  **Await Frontend Implementation (External):** The next step requires the separate frontend team to implement the UI changes based on the briefing document (`memory-bank/frontend_briefing_model_switcher.md`).
2.  **(Internal - Planned):** Address minor cleanups, implement comparison mode, perform testing (including model switcher once frontend is ready).

## 4. Active Decisions & Guiding Principles

*   **Model Configuration (`RunConfig`):** Use nested `ModelConfig` with provider-specific Pydantic parameter models and validation. (Implemented).
*   **API Key Management:** Backend fetches keys from `keystore.py` based on `provider` at runtime; keys are NOT part of `RunConfig`. (Implemented).
*   **Incremental Implementation:** Implement model switcher in phases (Config -> Logic -> Frontend Briefing). (Backend Phases Complete).
*   **Output Handling:** Focus on standard text output initially; defer handling extra metadata/thinking.
*   **Frontend/Backend Split:** Backend changes documented in briefing for the separate frontend team.
*   **Strict Error Handling:** Backend logic fails loudly on invalid/missing configuration or API keys. (Implemented).
*   **Adhere to `refactor_plan.md` (General):** Continue following established architecture principles where applicable.
*   **CRITICAL: NO GUESSING / ASSUMPTIONS:** Verify all assumptions. (Mistake Tally Increased)
*   **Focus:** Complete current task before moving to next major feature.
*   **Simplicity/Minimalism (Custom Code):** Write direct, functional custom code.
*   **Strict Commenting:** Follow the detailed policy in `systemPatterns.md`.
*   **Types as Source of Truth:** Update type definition files first.

## 5. Recent Learnings & Mistakes (To Avoid Repetition)

*   **Refactoring Order:** Frontend MUST wait for backend API/data layers. (Mistake Tally: 2)
*   **NO GUESSING / Assumptions:** Strictly adhere. (Mistake Tally: 5)
*   **Global Types (`global.d.ts`):** Globally available. (Mistake Tally: 1)
*   **Strict Commenting:** Avoid narrative/obvious comments. (Mistake Tally: 6)
*   **No Placeholders:** Implement directly. (Mistake Tally: 3)
*   **Store Integrity:** Don't remove essential exports. (Mistake Tally: 1)
*   **Tool Usage (`apply_diff` / `replace_in_file`):** Re-read file or use smaller diffs if errors occur. (Mistake Tally: 8)
*   **Tool Usage (`write_to_file`):** Do not include tool-specific markers. (Mistake Tally: 1)
*   **State Management Complexity:** Avoid unnecessary stores. (Mistake Tally: 1)
*   **Follow Instructions:** Confirm understanding before acting. (Mistake Tally: 1)
*   **Tool Use Discipline:** MUST use a tool when required. (Mistake Tally: 1)
*   **Plan Ambiguity:** Plans MUST be decisive. (Mistake Tally: 1)
*   **Code Reusability:** Extract reusable logic. (Mistake Tally: 1)
*   **Task Interruption:** Ensure memory reflects state at handoff. (Mistake Tally: 1)
*   **Conceptual Integrity:** Don't mix frontend/backend state representations. (Mistake Tally: 1)
*   **Plan Alignment:** Implement strictly according to plan. (Mistake Tally: 1)
*   **Component Responsibility:** Keep UI components focused. (Mistake Tally: 2)
*   **State Derivation:** Correctly identify source of truth. (Mistake Tally: 2)
*   **Clarity over Premature Action:** Discuss fully before implementation. (Mistake Tally: 2)
*   **Verify Types:** Check definitions. (Mistake Tally: 2)
*   **Component Prop Types:** Use defined types correctly. (Mistake Tally: 1)
*   **Backend Imports:** Ensure correct imports. (Mistake Tally: 6)
*   **Pydantic Validation:** Understand nuances. (Mistake Tally: 1)
*   **Mode Restrictions:** Be aware of restrictions. (Mistake Tally: 2)
*   **Server Caching:** Remember restart may be needed. (Mistake Tally: 1)
*   **Data Source Confusion:** Distinguish `CheckpointTuple`/`StateSnapshot`. (Mistake Tally: 3)
*   **Delegation Efficiency:** Provide context or update memory directly. (Mistake Tally: 1)
*   **Error Handling:** Implement strict/loud error handling as requested, not silent fallbacks. (Mistake Tally: 1)

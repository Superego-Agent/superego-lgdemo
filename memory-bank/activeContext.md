# Active Context: Superego LangGraph Agent (As of 2025-04-28 ~02:57 PM)

## 1. Current Major Focus: Feature - Model Switcher Implementation (Phase 1)

*   **Goal:** Implement the backend configuration and storage mechanism for selecting different LLM providers and models via the `RunConfig`.
*   **Status:** Planning complete. Ready to start Phase 1 implementation.

## 2. Recent Changes (During Current Session)

*   **Model Switcher Planning:**
    *   Investigated current `RunConfig` (constitution) storage mechanism (stored in LangGraph `configurable`).
    *   Investigated configuration requirements for various LLM providers (Anthropic, Google, OpenAI, OpenAI-compatible, OpenRouter).
    *   Defined V2 `RunConfig` structure:
        *   Nested `ModelConfig` within `RunConfig`.
        *   `ModelConfig` contains `provider` (Literal), `name` (str), and provider-specific parameter models (e.g., `OpenAIParams`, `GoogleVertexParams`).
        *   Pydantic validator to ensure correct parameter model population based on `provider`.
        *   **No API key info stored in `RunConfig`**.
    *   Confirmed API keys will be handled by backend logic, fetching from `keystore.py` based on `provider`.
    *   Investigated LangGraph's handling of intermediate "thinking" steps (relies on LLM output, tool calls tracked). Decided to defer detailed "thinking" display.
    *   Acknowledged frontend is in a separate repository and will require a briefing after backend work.
    *   Finalized multi-phase implementation plan (see `progress.md`).

## 3. Immediate Next Steps

1.  **Implement Model Switcher - Phase 1 (Steps 1 & 2):**
    *   **Subtask:** Modify `backend_models.py` to define the V2 `ModelConfig` and update `RunConfig`, including provider-specific parameter models and the Pydantic validator.
    *   **Subtask:** Update the `/api/runs/stream` endpoint in `api_routers/runs.py` to accept the new `RunConfig` structure, serialize `ModelConfig`, and store it under `"model_config"` in the LangGraph `configurable` dictionary.

## 4. Active Decisions & Guiding Principles

*   **Model Configuration (`RunConfig`):** Use nested `ModelConfig` with provider-specific Pydantic parameter models and validation.
*   **API Key Management:** Backend fetches keys from `keystore.py` based on `provider` at runtime; keys are NOT part of `RunConfig`.
*   **Incremental Implementation:** Implement model switcher in phases (Config -> Logic -> Frontend Briefing).
*   **Output Handling:** Focus on standard text output initially; defer handling extra metadata/thinking.
*   **Frontend/Backend Split:** Backend changes must be clearly documented for the separate frontend team.
*   **Adhere to `refactor_plan.md` (General):** Continue following established architecture principles where applicable.
*   **CRITICAL: NO GUESSING / ASSUMPTIONS:** Verify all assumptions about APIs, configurations, types, and behavior. Check source code or ask. (Mistake Tally Increased)
*   **Focus:** Complete current task before moving to next major feature.
*   **Simplicity/Minimalism (Custom Code):** Write direct, functional custom code.
*   **Strict Commenting:** Follow the detailed policy in `systemPatterns.md`.
*   **Types as Source of Truth:** Update type definition files first.

## 5. Recent Learnings & Mistakes (To Avoid Repetition)

*   **Refactoring Order:** Frontend component refactoring MUST wait until the backend API contract is verified AND the underlying data/processing layers are implemented. (Mistake Tally: 2)
*   **NO GUESSING / Assumptions:** Strictly adhere to this rule. (Mistake Tally: 5)
*   **Global Types (`global.d.ts`):** Types are globally available; explicit imports are incorrect. (Mistake Tally: 1)
*   **Strict Commenting:** Avoid narrative/obvious comments. (Mistake Tally: 6)
*   **No Placeholders:** Do not introduce placeholders. Implement required functionality directly. (Mistake Tally: 3)
*   **Store Integrity:** Ensure essential exports are not accidentally removed. (Mistake Tally: 1)
*   **Tool Usage (`apply_diff` / `replace_in_file`):** Re-read file or use smaller diffs if errors occur. (Mistake Tally: 8)
*   **Tool Usage (`write_to_file`):** Do not include tool-specific markers. (Mistake Tally: 1)
*   **State Management Complexity:** Avoid unnecessary intermediate stores. (Mistake Tally: 1)
*   **Follow Instructions:** Confirm understanding before acting. (Mistake Tally: 1)
*   **Tool Use Discipline:** MUST use a tool in every response when required. (Mistake Tally: 1)
*   **Plan Ambiguity:** Plans MUST be decisive and unambiguous. (Mistake Tally: 1)
*   **Code Reusability:** Extract reusable logic. (Mistake Tally: 1)
*   **Task Interruption:** Ensure memory/plan accurately reflects the state at handoff. (Mistake Tally: 1)
*   **Conceptual Integrity:** Do not mix frontend state with backend state representations. (Mistake Tally: 1)
*   **Plan Alignment:** Ensure implementation actions strictly follow the agreed-upon plan. (Mistake Tally: 1)
*   **Component Responsibility:** Keep UI components focused. (Mistake Tally: 2)
*   **State Derivation:** Correctly identify the source of truth for UI state. (Mistake Tally: 2)
*   **Clarity over Premature Action:** Fully discuss and clarify plan details before implementation. (Mistake Tally: 2)
*   **Verify Types:** Always check type definitions. (Mistake Tally: 2)
*   **Component Prop Types:** Ensure component props use defined types correctly. (Mistake Tally: 1)
*   **Backend Imports:** Ensure all necessary modules are imported correctly. (Mistake Tally: 6)
*   **Pydantic Validation:** Understand validation nuances (e.g., `Union`). (Mistake Tally: 1)
*   **Mode Restrictions:** Be aware of file editing restrictions. (Mistake Tally: 2)
*   **Server Caching:** Remember backend changes may require server restart. (Mistake Tally: 1)
*   **Data Source Confusion:** Distinguish between `CheckpointTuple` and `StateSnapshot`. (Mistake Tally: 3)
*   **Delegation Efficiency:** Provide sufficient context or perform updates directly when appropriate for memory files. (Mistake Tally: 1)

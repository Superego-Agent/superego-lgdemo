 # Active Context: Superego LangGraph Agent (As of 2025-04-10 ~02:55 AM)

## 1. Current Major Focus: COMPLETE - Frontend State Refactor & History Fix

*   **Goal:** Implement the new frontend state management architecture outlined in `refactor_plan.md` and ensure `nodeId` is correctly associated with messages loaded from history.
*   **Status:** **COMPLETED**. The refactor based on `refactor_plan.md` is done, and the `nodeId` issue in history loading has been resolved.

## 2. Recent Changes (During Current Session)

*   **Frontend State Refactor:** Completed all steps outlined in `refactor_plan.md`, including store updates, API layer changes, stream processing, and UI component refactoring (`ChatView`, `ChatInterface`, `ConstitutionSelector`, `chatService`).
*   **Constitution Handling:** Implemented global store and service layer (`chatService.ts`) for managing constitution selection and API calls.
*   **Various Frontend Fixes:** Addressed `svelte-check` errors, updated `MessageCard` props, integrated global constitution loading.
*   **Backend History `nodeId` Fix:**
    *   Investigated why `nodeId` was missing for history messages, particularly for `inner_agent`.
    *   Confirmed via inspection (`inspect_checkpoint.py`) that `StateSnapshot` contains `msg.name` but it was `None` for `inner_agent` messages.
    *   Identified that `inner_agent` node function in `inner_agent_definitions.py` was not setting `msg.name`.
    *   Updated `inner_agent_definitions.py` to explicitly set `response.name = "inner_agent"`.
    *   Refactored `api_routers/threads.py` to use `StateSnapshot` (via `graph.aget_state`/`aget_state_history`) and rely on `msg.name` (with exception for `HumanMessage`) for `nodeId`.
    *   Fixed `ImportError` for `StateSnapshot` in `api_routers/threads.py` after several attempts.
    *   Fixed `ValidationError` in `api_routers/runs.py` for initial `HumanMessage` `nodeId`.
    *   Resolved final 500 error by ensuring `inner_agent` name was set and correctly processed in history adaptation.

## 3. Immediate Next Steps

1.  **Small Cleanups:** Address minor code improvements or pending issues identified during refactoring (Details TBD by user).
2.  **Implement Comparison Mode:** Develop the side-by-side run comparison feature (Details TBD by user).
3.  **(Future):** Config CRUD, Output Superego, etc.

## 4. Active Decisions & Guiding Principles

*   **Adhere to `refactor_plan.md`:** Strictly follow the updated architecture and principles.
*   **Refactoring Order:** Types -> Stores -> API Layer -> Stream Processor -> UI Components.
*   **State Management:** Use the central `threadCacheStore` holding `ThreadCacheData`. UI components derive view from this cache. `api.ts` manages cache updates.
*   **SSE Consolidation:** `run_start` is the sole source of initial thread info; `thread_info` event is eliminated.
*   **Type-Safe Dispatch:** Use a typed handler map in `api.ts` for SSE event processing.
*   **CRITICAL: NO GUESSING / ASSUMPTIONS:** Verify all assumptions about APIs, configurations, types, and behavior. Check source code (`global.d.ts`, backend) or ask. Do not invent types or logic. (Mistake Tally Increased)
*   **Focus:** Complete current task before moving to next major feature.
*   **Simplicity/Minimalism (Custom Code):** Write direct, functional custom code. Handle realistic errors cleanly, but avoid excessive defensive coding.
*   **No Data Migration:** Ignore/discard old `localStorage` data.
*   **Strict Commenting:** Follow the detailed policy in `systemPatterns.md`. NO narrative/ephemeral comments. NO explaining the obvious. (Mistake Tally Increased)
*   **Declarative Svelte:** Use Svelte's reactivity system.
*   **Types as Source of Truth:** Update type definition files first.

## 5. Recent Learnings & Mistakes (To Avoid Repetition)

*   **Refactoring Order:** Frontend component refactoring MUST wait until the backend API contract is verified AND the underlying data/processing layers (cache, stream processor, API integration) are implemented. Attempting UI changes first leads to rework. (Mistake Tally: 2)
*   **NO GUESSING / Assumptions:** Strictly adhere to this rule. Do not use speculative language. Verify facts. (Mistake Tally: 4)
*   **Global Types (`global.d.ts`):** Types are globally available; explicit imports are incorrect. (Mistake Tally: 1)
*   **Strict Commenting:** Avoid narrative/obvious comments. No placeholders. (Mistake Tally: 5)
*   **No Placeholders:** Do not introduce placeholders or vague comments during refactoring. Implement required functionality directly or leave it clearly broken until dependencies are met. (Mistake Tally: 3)
*   **Store Integrity:** Ensure essential exports are not accidentally removed. (Mistake Tally: 1)
*   **Tool Usage (`apply_diff` / `replace_in_file`):** Tool can be unreliable for multi-part or complex diffs, especially after partial applications or file reversions. Re-read file or use smaller diffs if errors occur. (Mistake Tally: 8 - Repeated diff failures, including on `activeContext.md`)
*   **Tool Usage (`write_to_file`):** Do not include tool-specific markers. (Mistake Tally: 1)
*   **State Management Complexity:** Avoid creating unnecessary intermediate stores when a simpler approach exists. Keep state management lean. (Mistake Tally: 1)
*   **Follow Instructions:** Do not proceed with coding or tool use when asked to discuss or plan further. Confirm understanding before acting. (Mistake Tally: 1)
*   **Tool Use Discipline:** MUST use a tool in every response when required, even if just discussing plans. (Mistake Tally: 1)
*   **Plan Ambiguity:** Plans (like `refactor_plan.md`) MUST be decisive and unambiguous. Avoid "e.g." or other vague language. (Mistake Tally: 1)
*   **Code Reusability:** Identify and extract reusable logic (like `prepare_sse_event`) into shared utility files (`utils.py`) instead of keeping it local. (Mistake Tally: 1)
*   **Task Interruption:** Be prepared for interruptions and ensure memory/plan accurately reflects the state at handoff. (Mistake Tally: 1)
*   **Conceptual Integrity:** Do not add transient frontend state (like `isStreaming`) directly to data structures representing backend state (`HistoryEntry`). Use wrapper objects (`ThreadCacheData`) or separate stores if necessary. (Mistake Tally: 1)
*   **Plan Alignment:** Ensure implementation actions strictly follow the agreed-upon plan. Do not introduce unapproved elements (like the run config display in `ChatView`). (Mistake Tally: 1)
*   **Component Responsibility:** Keep UI components focused. Display logic belongs in display components (`ChatView`), container logic in containers (`ChatInterface`). Avoid placeholders for missing content in display components. (Mistake Tally: 2)
*   **State Derivation:** Correctly identify the source of truth for UI state (e.g., streaming status comes from the cache managed by `api.ts`, not component-local flags). (Mistake Tally: 2)
*   **Clarity over Premature Action:** Fully discuss and clarify plan details before attempting implementation, especially when user feedback indicates confusion or disagreement. (Mistake Tally: 2)
*   **Verify Types:** Always check `global.d.ts` for correct types before using them. Do not invent types. (Mistake Tally: 2)
*   **Component Prop Types:** Ensure component props (`MessageCard`'s `message` prop) correctly use defined types and internal logic respects the type structure (e.g., using `message.type` not `message.sender`). (Mistake Tally: 1)
*   **Backend Imports:** Ensure all necessary models/modules (e.g., Pydantic models for SSE, `json`, `StateSnapshot`) are imported in backend Python files using the correct path. (Mistake Tally: 6)
*   **Pydantic Validation:** Understand how to validate Pydantic models, especially `Union` types. `model_validate` cannot be called directly on a `Union`. (Mistake Tally: 1)
*   **Mode Restrictions:** Be aware of file editing restrictions in different modes (e.g., Architect mode cannot edit `.py` files). Switch modes when necessary. (Mistake Tally: 1)
*   **Server Caching:** Remember that backend server changes (especially Python code) may require a server restart to take effect due to caching (`.pyc` files, module caching). (Mistake Tally: 1)
*   **Data Source Confusion:** Clearly distinguish between `CheckpointTuple` (from `aget_tuple`) and `StateSnapshot` (from `aget_state`). Use the correct data source as instructed. (Mistake Tally: 3)

# Active Context: Superego LangGraph Agent (As of 2025-04-09 Evening)

## 1. Current Major Focus: Frontend State Refactor

*   **Goal:** Implement the new frontend state management architecture outlined in `refactor_plan.md`.
*   **Motivation:** Establish a robust foundation aligned with backend checkpointing to enable future features like compare mode, simplify state, and improve clarity. Discard old `localStorage` structure.
*   **Key Concept:** Frontend acts as a thin client. A central `historyCacheStore` holds the latest known `HistoryEntry` for each thread. UI components subscribe to this cache and display data for relevant `threadId`(s) passed via props. Optimistic updates modify the cache directly during streaming, with the final state fetched from the backend overwriting the cache entry on stream completion.

## 2. Recent Changes (Since last update)

*   **Backend API Verification:** Verified backend API endpoints (`api_routers/runs.py`, `api_routers/threads.py`) against `refactor_plan.md` Section 4 requirements. Confirmed alignment.
*   **Backend Server Cleanup (`backend_server_async.py`):** Refactored to use FastAPI routers correctly.
*   **Plan Refinement (`refactor_plan.md`):** Updated the implementation plan to adopt the `historyCacheStore` approach for state management and direct optimistic updates, clarifying the refactoring order (Cache -> Processor -> API -> UI).

## 3. Immediate Next Steps (Refined Refactor Order)

1.  **Define `historyCacheStore`:** Add the non-persisted `historyCacheStore: Writable<Record<string, HistoryEntry>>` to `src/lib/stores.ts`.
2.  **Implement Stream Processor:** Create `src/lib/streamProcessor.ts` with pure functions (`handleChunk`, `handleToolChunk`, `handleToolResult`) that take a `HistoryEntry` and event data, returning a new, updated `HistoryEntry`.
3.  **Integrate API:** Modify `src/lib/api.ts` (`streamRun` function) to:
    *   Call `streamProcessor.ts` functions upon receiving intermediate SSE events.
    *   Update the `historyCacheStore` with the optimistically modified `HistoryEntry`.
    *   Trigger `getLatestHistory` on the `onEnd` callback and overwrite the cache entry, logging any discrepancies.
4.  **Refactor UI Components:**
    *   Update `ChatInterface.svelte` (and future components like `CompareInterface`) to:
        *   Receive `threadId`(s) via props.
        *   Subscribe to `historyCacheStore`.
        *   Select and display data reactively based on props (`$historyCacheStore[threadId]`).
        *   Trigger `getLatestHistory` if data for a required `threadId` is not in the cache.
        *   Call the updated `streamRun` API function, passing necessary callbacks (`onEnd`, `onError`, etc., but *not* handling intermediate events directly).
    *   Refactor `ConstitutionSelector.svelte` to manage its state and provide the `RunConfig` (placeholder used initially in `ChatInterface`).
5.  **Testing:** Test the complete workflow with the new architecture.

## 4. Active Decisions & Guiding Principles

*   **Adhere to `refactor_plan.md`:** Strictly follow the architecture and principles outlined, including the `historyCacheStore` approach.
*   **Refactoring Order:** API -> Transformation -> UI. Verify lower layers before building dependent layers.
*   **State Management:** Use the central `historyCacheStore` for thread states. UI components derive their view from this cache based on `threadId` props. Avoid unnecessary intermediate stores (like `activeHistoryEntryStore`).
*   **Optimistic Updates:** Update the `historyCacheStore` directly during streaming based on processed SSE events. Overwrite with fetched final state on stream end.
*   **CRITICAL: NO GUESSING:** Verify all assumptions about APIs, configurations, and behavior. Ask if unsure.
*   **Focus:** Complete the state refactor to enable compare mode.
*   **Simplicity/Minimalism (Custom Code):** Write direct, functional custom code.
*   **No Data Migration:** Ignore/discard old `localStorage` data.
*   **Strict Commenting:** Follow the detailed policy in `systemPatterns.md`.
*   **Declarative Svelte:** Use Svelte's reactivity system.

## 5. Recent Learnings & Mistakes (To Avoid Repetition)

*   **Refactoring Order:** Frontend component refactoring MUST wait until the backend API contract is verified AND the underlying data/processing layers (cache, stream processor, API integration) are implemented. Attempting UI changes first leads to rework. (Mistake Tally: 2 - Previous attempt + starting ChatInterface refactor too early)
*   **NO GUESSING / Assumptions:** Strictly adhere to this rule. Do not use speculative language. Verify facts. (Mistake Tally: 2)
*   **Global Types (`global.d.ts`):** Types are globally available; explicit imports are incorrect. (Mistake Tally: 1)
*   **Strict Commenting:** Avoid narrative/obvious comments. No placeholders. (Mistake Tally: 2 - Previous + adding placeholders/vague comments in proposed diff)
*   **No Placeholders:** Do not introduce placeholders or vague comments during refactoring. Implement required functionality directly or leave it clearly broken until dependencies are met. (Mistake Tally: 2 - Previous + adding placeholders/vague comments in proposed diff)
*   **Store Integrity:** Ensure essential exports are not accidentally removed. (Mistake Tally: 1)
*   **Tool Usage (`apply_diff`):** Be cautious with multi-block diffs; re-read file if partial application occurs. (Mistake Tally: 2 - Previous + failure to re-read after partial failure)
*   **Tool Usage (`write_to_file`):** Do not include tool-specific markers. (Mistake Tally: 1)
*   **State Management Complexity:** Avoid creating unnecessary intermediate stores (e.g., `activeHistoryEntryStore`, `streamingStateStore`) when a simpler approach (direct cache updates + derived UI) exists. Keep state management lean. (Mistake Tally: 1)
*   **Follow Instructions:** Do not proceed with coding or tool use when asked to discuss or plan further. Confirm understanding before acting. (Mistake Tally: 1)

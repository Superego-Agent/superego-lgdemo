 # Active Context: Superego LangGraph Agent (As of 2025-04-09 ~10:30 PM)

## 1. Current Major Focus: Frontend State Refactor

*   **Goal:** Implement the new frontend state management architecture outlined in `refactor_plan.md`.
*   **Motivation:** Establish a robust foundation aligned with backend checkpointing to enable future features like compare mode, simplify state, and improve clarity. Discard old `localStorage` structure.
*   **Key Concept:** Frontend acts as a thin client. A central `threadCacheStore` holds `ThreadCacheData` (containing `history`, `isStreaming`, `error`) for each thread. UI components subscribe to this cache and display data for relevant `threadId`(s). `api.ts` manages updates to this cache based on API calls and SSE events.

## 2. Recent Changes (Since last update)

*   **Type Definitions Updated:** Modified `global.d.ts` and `backend_models.py` to add `ThreadCacheData` interface/concept and remove redundant `SSEThreadInfoData` type/model, consolidating into `SSERunStartData`.
*   **Plan Refinement (`refactor_plan.md`):** Updated plan to adopt `threadCacheStore` with `ThreadCacheData`, consolidate SSE events (`run_start` only), mandate type-safe event dispatch in `api.ts`, prune outdated/verbose sections, and emphasize types-first principle.

## 3. Immediate Next Steps (Refined Refactor Order)

1.  **Update Stores (`src/lib/stores.ts`):** Rename `historyCacheStore` to `threadCacheStore` and update type to use `ThreadCacheData`.
2.  **Update API Layer (`src/lib/api.ts`):** Refactor to use `threadCacheStore`, `ThreadCacheData`, implement type-safe event dispatch map, remove `thread_info` handling, manage state flags robustly.
3.  **Update Stream Processor (`src/lib/streamProcessor.ts`):** Ensure mutators work with `HistoryEntry` extracted from `ThreadCacheData.history`.
4.  **Create `ChatView.svelte` Component:** Implement component to display thread state based on `threadCacheStore`.
5.  **Refactor `ChatInterface.svelte` Component:** Update to use `ChatView`, simplify `handleSend`.
6.  **Refactor `ConstitutionSelector.svelte`:** (Lower priority) Update to provide `RunConfig`.
7.  **Testing:** Test the core workflows.

## 4. Active Decisions & Guiding Principles

*   **Adhere to `refactor_plan.md`:** Strictly follow the updated architecture and principles.
*   **Refactoring Order:** Types (`global.d.ts`, `backend_models.py`) -> Stores -> API Layer -> Stream Processor -> UI Components.
*   **State Management:** Use the central `threadCacheStore` holding `ThreadCacheData`. UI components derive view from this cache. `api.ts` manages cache updates.
*   **SSE Consolidation:** `run_start` is the sole source of initial thread info; `thread_info` event is eliminated.
*   **Type-Safe Dispatch:** Use a typed handler map in `api.ts` for SSE event processing.
*   **CRITICAL: NO GUESSING:** Verify all assumptions about APIs, configurations, and behavior. Ask if unsure.
*   **Focus:** Complete the state refactor to enable compare mode.
*   **Simplicity/Minimalism (Custom Code):** Write direct, functional custom code. Handle realistic errors cleanly, but avoid excessive defensive coding.
*   **No Data Migration:** Ignore/discard old `localStorage` data.
*   **Strict Commenting:** Follow the detailed policy in `systemPatterns.md`. No narrative/ephemeral comments.
*   **Declarative Svelte:** Use Svelte's reactivity system.
*   **Types as Source of Truth:** Update type definition files first.

## 5. Recent Learnings & Mistakes (To Avoid Repetition)

*   **Refactoring Order:** Frontend component refactoring MUST wait until the backend API contract is verified AND the underlying data/processing layers (cache, stream processor, API integration) are implemented. Attempting UI changes first leads to rework. (Mistake Tally: 2)
*   **NO GUESSING / Assumptions:** Strictly adhere to this rule. Do not use speculative language. Verify facts. (Mistake Tally: 2)
*   **Global Types (`global.d.ts`):** Types are globally available; explicit imports are incorrect. (Mistake Tally: 1)
*   **Strict Commenting:** Avoid narrative/obvious comments. No placeholders. (Mistake Tally: 3 - Added narrative comments again)
*   **No Placeholders:** Do not introduce placeholders or vague comments during refactoring. Implement required functionality directly or leave it clearly broken until dependencies are met. (Mistake Tally: 3)
*   **Store Integrity:** Ensure essential exports are not accidentally removed. (Mistake Tally: 1)
*   **Tool Usage (`apply_diff`):** Tool can be unreliable for multi-part or complex diffs; `write_to_file` may be necessary as a fallback, requiring careful reconstruction of the entire file. (Mistake Tally: 3 - Repeated diff failures)
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

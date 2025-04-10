 # Active Context: Superego LangGraph Agent (As of 2025-04-10 ~12:35 AM)

## 1. Current Major Focus: Frontend State Refactor

*   **Goal:** Implement the new frontend state management architecture outlined in `refactor_plan.md`.
*   **Motivation:** Establish a robust foundation aligned with backend checkpointing to enable future features like compare mode, simplify state, and improve clarity. Discard old `localStorage` structure.
*   **Key Concept:** Frontend acts as a thin client. A central `threadCacheStore` holds `ThreadCacheData` (containing `history`, `isStreaming`, `error`) for each thread. UI components subscribe to this cache and display data for relevant `threadId`(s). `api.ts` manages updates to this cache based on API calls and SSE events.

## 2. Recent Changes (During Current Session)

*   **Frontend State Refactor Progress:**
    *   Verified Step 2 (`stores.ts`) was already complete.
    *   Completed Step 3 (`api.ts` refactor for `ThreadCacheData`, SSE handling).
    *   Verified Step 4 (`streamProcessor.ts`) required no changes.
    *   Completed Step 5 (Created `ChatView.svelte`, using `MessageCard`).
    *   Completed Step 6 (`ChatInterface.svelte` refactor, including pagination layout).
*   **Constitution Handling Approach Change:** Decided to use a global store (`globalConstitutionsStore.ts`) for fetching/managing available global constitutions instead of component-level fetching in `ConstitutionSelector.svelte`.
*   **API Updates:** Added `fetchAvailableConstitutions` and `fetchConstitutionContent` to `api.ts`.
*   **Global Loading:** Integrated `loadGlobalConstitutions` call into `App.svelte` onMount.
*   **`MessageCard.svelte` Refactor:** Updated component to correctly use `message.type` and `message.nodeId` instead of non-existent `sender`/`node` props, adhering strictly to `MessageType` definitions. Replaced type assertions with guards.
*   **`svelte-check` Fixes:** Addressed various errors/warnings (unused CSS, accessibility, TS errors) across multiple frontend components (`Sidebar`, `ConstitutionInfoModal`, `AddConstitutionModal`, `ConstitutionSelector`, `CompareInterface`, `ConstitutionDropdown`).
*   **Backend SSE Fixes:** Resolved `NameError` issues in `api_routers/runs.py` and `api_routers/threads.py` related to missing imports (`SSERunStartData`, `SSEErrorData`, `SSEChunkData`, `HumanApiMessageModel`, `json`) and incorrect type validation.

## 3. Immediate Next Steps (Refined Refactor Order)

1.  ~~**Update Stores (`src/lib/stores.ts`)**~~ (Verified Complete)
2.  ~~**Update API Layer (`src/lib/api.ts`)**~~ (Completed)
3.  ~~**Update Stream Processor (`src/lib/streamProcessor.ts`)**~~ (Verified Complete)
4.  ~~**Create `ChatView.svelte` Component**~~ (Completed)
5.  ~~**Refactor `ChatInterface.svelte` Component**~~ (Completed, including pagination)
6.  **Refactor Constitution Handling & Sending Logic (Completed):**
    *   Verified `ConstitutionSelector.svelte` uses stores and dispatches `configChange`. (Completed)
    *   Created `src/lib/services/chatService.ts` to manage config state (`currentRunConfigModules` store) and API calls (`sendUserMessage`). (Completed)
    *   Refactored `ChatInterface.svelte` to call `chatService.updateChatConfig` on `configChange` and `chatService.sendUserMessage` in `handleSend`. (Completed)
7.  **Testing:** Thoroughly test the core chat workflow after recent fixes.
8.  **(Future):** Compare Mode, Config CRUD, Output Superego, etc.

## 4. Active Decisions & Guiding Principles

*   **Adhere to `refactor_plan.md`:** Strictly follow the updated architecture and principles.
*   **Refactoring Order:** Types -> Stores -> API Layer -> Stream Processor -> UI Components. (Generally followed, but ConstitutionSelector refactor involves stores/API/component interaction).
*   **State Management:** Use the central `threadCacheStore` holding `ThreadCacheData`. UI components derive view from this cache. `api.ts` manages cache updates.
*   **SSE Consolidation:** `run_start` is the sole source of initial thread info; `thread_info` event is eliminated.
*   **Type-Safe Dispatch:** Use a typed handler map in `api.ts` for SSE event processing.
*   **CRITICAL: NO GUESSING / ASSUMPTIONS:** Verify all assumptions about APIs, configurations, types, and behavior. Check source code (`global.d.ts`, backend) or ask. Do not invent types or logic. (Mistake Tally Increased)
*   **Focus:** Complete the state refactor to enable compare mode.
*   **Simplicity/Minimalism (Custom Code):** Write direct, functional custom code. Handle realistic errors cleanly, but avoid excessive defensive coding.
*   **No Data Migration:** Ignore/discard old `localStorage` data.
*   **Strict Commenting:** Follow the detailed policy in `systemPatterns.md`. NO narrative/ephemeral comments. NO explaining the obvious. (Mistake Tally Increased)
*   **Declarative Svelte:** Use Svelte's reactivity system.
*   **Types as Source of Truth:** Update type definition files first.

## 5. Recent Learnings & Mistakes (To Avoid Repetition)

*   **Refactoring Order:** Frontend component refactoring MUST wait until the backend API contract is verified AND the underlying data/processing layers (cache, stream processor, API integration) are implemented. Attempting UI changes first leads to rework. (Mistake Tally: 2) **Note:** Addressed `handleSend` refactor early based on user feedback for better separation of concerns.
*   **NO GUESSING / Assumptions:** Strictly adhere to this rule. Do not use speculative language. Verify facts. (Mistake Tally: 4 - Repeatedly assumed types/logic for ConstitutionSelector)
*   **Global Types (`global.d.ts`):** Types are globally available; explicit imports are incorrect. (Mistake Tally: 1)
*   **Strict Commenting:** Avoid narrative/obvious comments. No placeholders. (Mistake Tally: 5 - Repeatedly added narrative comments)
*   **No Placeholders:** Do not introduce placeholders or vague comments during refactoring. Implement required functionality directly or leave it clearly broken until dependencies are met. (Mistake Tally: 3)
*   **Store Integrity:** Ensure essential exports are not accidentally removed. (Mistake Tally: 1)
*   **Tool Usage (`apply_diff`):** Tool can be unreliable for multi-part or complex diffs, especially after partial applications. Re-read file if errors occur. (Mistake Tally: 5 - Repeated diff failures)
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
*   **Verify Types:** Always check `global.d.ts` for correct types before using them. Do not invent types. (Mistake Tally: 2 - Invented `ConstitutionInfo`, `DisplayConstitution`)
*   **Component Prop Types:** Ensure component props (`MessageCard`'s `message` prop) correctly use defined types and internal logic respects the type structure (e.g., using `message.type` not `message.sender`). (Mistake Tally: 1 - Corrected in `MessageCard`)
*   **Backend Imports:** Ensure all necessary models/modules (e.g., Pydantic models for SSE, `json`) are imported in backend Python files. (Mistake Tally: 3 - Missed `SSERunStartData`, `SSEErrorData`, `SSEChunkData`, `HumanApiMessageModel`, `json` in API routers)
*   **Pydantic Validation:** Understand how to validate Pydantic models, especially `Union` types. `model_validate` cannot be called directly on a `Union`. (Mistake Tally: 1 - Tried `MessageTypeModel.model_validate`)
*   **Tool Usage (`apply_diff`):** Re-read file content if `apply_diff` fails due to mismatch, even if the system reports success on a previous step. (Mistake Tally: 1 - Failed diff on `api_routers/threads.py`)
*   **Mode Restrictions:** Be aware of file editing restrictions in different modes (e.g., Architect mode cannot edit `.py` files). Switch modes when necessary. (Mistake Tally: 1 - Attempted Python edit in Architect mode)
*   **Server Caching:** Remember that backend server changes (especially Python code) may require a server restart to take effect due to caching (`.pyc` files, module caching). (Mistake Tally: 1 - Backend ran old code after file update)

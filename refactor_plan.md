# Frontend State Architecture Plan: Checkpoint-Centric

## 1. Introduction & Motivation

### Goal

This document outlines the frontend state management architecture designed to align closely with the backend's LangGraph checkpointing system. The primary goals are:

*   Establish a robust foundation for features like side-by-side comparison of different agent runs ("Compare" toggle for processing multiple runs at once from a single input).
*   Simplify state management by leveraging the backend checkpointer as the primary source of truth for conversation history and run-specific configurations.
*   Ensure future flexibility for incorporating advanced LangGraph features like time-travel and branching.
*   Maintain a clear separation between UI presentation concerns and backend execution data.

### Core Idea

The frontend acts as a thin client. Conversation history and run-specific details (like the configuration used) are persisted within LangGraph checkpoints on the backend. The frontend fetches this checkpoint data as needed to display conversations. UI sessions are managed locally, mapping UI tabs to backend conversation threads.

## 2. Guiding Principles (CRITICAL)

This architecture adheres to the following strict principles:

*   **Focus:** The primary goal is establishing the new state structure to enable future features, particularly a clean compare mode. Functionality should remain unchanged from the user's perspective *before* compare mode is explicitly built upon this new foundation.
*   **Simplicity:** Code MUST be direct and functional. Avoid unnecessary complexity, deep conditional nesting, or OOP patterns where simpler procedural or functional approaches suffice. Keep it lean.
*   **Minimalism:** This is a refactor for a research demo app, not a production system. Features and error handling beyond the absolute minimum required for the core goal WILL be omitted. Handle realistic API/stream errors cleanly, but **NO extraneous defensive coding** for unlikely edge cases.
*   **No Data Migration:** Existing `localStorage` data (`superego_conversations`) will be **ignored and discarded**. Users will start with a clean slate. No time will be wasted on migration code.
*   **Strict Commenting Policy:** Comments are **ONLY** permitted if they provide permanent, essential clarification for non-obvious logic that cannot be made clearer through better naming or structure. **NO ephemeral comments, NO placeholder TODOs, NO explaining the obvious.** Adding comments requires extreme caution and justification. This is non-negotiable.
*   **Derived State:** Minimize persisted frontend state. Avoid storing data that can be derived from fetched backend checkpoints (e.g., message history, run configurations). Leverage Svelte's derived stores to compute view-specific data dynamically from the source-of-truth checkpoint data when a session is active.
*   **Types as Source of Truth:** Type definitions (`superego-frontend/src/global.d.ts` and `backend_models.py`) are the primary source of truth for data structures. They should be updated *first* when structures change, and code refactored to conform.

## 3. Architecture Overview

### Core Concepts

*   **Checkpoints (Backend):** The backend LangGraph checkpointer is the **single source of truth**. It saves snapshots (`StateSnapshot`) of the graph state (including messages) at each step of execution.
*   **`threadId` (Backend & Frontend):** A unique identifier (e.g., UUID string) managed by the backend checkpointer, linking all checkpoints belonging to a single continuous conversation thread.
*   **`configurable` Metadata (Backend):** When invoking the backend graph, the frontend includes custom metadata within the `configurable` dictionary. This metadata is persisted with the checkpoint by the checkpointer. Key custom metadata includes:
    *   `agentRunId`: A unique frontend-generated UUID identifying a specific interaction attempt (e.g., one user message and the subsequent agent response sequence).
    *   `frontendConfig`: An object containing the specific configuration (selected constitutions, adherence levels, etc.) used by the frontend for that `agentRunId`.
*   **`UISession` (Frontend):** Represents a UI tab or view. It maps a frontend-generated `sessionId` to one or more backend `threadId`s that should be displayed within that tab. This allows for single-thread views (standard chat) and multi-thread views (compare mode).
*   **`knownThreadIds` (Frontend):** A simple list stored in `localStorage` containing all `threadId`s that this specific client/browser has created or interacted with. Acts as a client-side index to filter relevant sessions/threads.

### Data Structures (Source of Truth: `superego-frontend/src/global.d.ts`)

All frontend TypeScript interfaces and types related to state management, API communication, and SSE events are defined in `superego-frontend/src/global.d.ts`. This file serves as the single source of truth for these structures. Key interfaces include:

*   `UISessionState`: Represents a UI tab/session and its associated backend `threadIds`.
*   `HistoryEntry`: Represents the content of a backend checkpoint (messages, run config).
*   `ThreadCacheData`: Wrapper object stored in the frontend cache, containing `HistoryEntry` plus frontend status flags (`isStreaming`, `error`).
*   `MessageType`: Union type for different message structures.
*   SSE Event Interfaces (`SSERunStartData`, `SSEChunkData`, etc.): Define the structure of data received via Server-Sent Events.

**Principle:** Type definitions (`global.d.ts` and `backend_models.py`) should always be updated *first* when the data structure changes. Code should then be refactored to conform to the updated types.

### Frontend State (`localStorage` & Stores)

```typescript
// Relevant stores defined in src/lib/stores.ts

// Persisted Stores (using svelte-persisted-store)
export const knownThreadIds: Writable<string[]>; // Index of known thread IDs
export const uiSessions: Writable<Record<string, UISessionState>>; // Maps UI session ID to state (including thread IDs)

// Non-Persisted Stores
export const activeSessionId: Writable<string | null>; // ID of the currently viewed UI session
export const threadCacheStore: Writable<Record<string, ThreadCacheData>>; // In-memory cache for thread data + status
export const globalError: Writable<string | null>; // Global error message display
```

### Backend State (Checkpointer)

*   The backend utilizes a LangGraph checkpointer (e.g., `AsyncSqliteSaver`) configured to persist graph state.
*   Checkpoints store the graph state (`values`, including messages), internal execution `metadata`, and the `configurable` dictionary passed during invocation (containing `thread_id`, `runConfig`).
*   Checkpoints are grouped by `threadId`.

## 4. Backend API Requirements

*   **/api/runs/stream Endpoint:**
    *   Accepts `input` and `configurable` (`CheckpointConfigurable`).
    *   `configurable` MUST contain `thread_id: string | null` and `runConfig: RunConfig`.
    *   Backend MUST pass `configurable` to LangGraph invocation.
    *   Backend MUST return `thread_id` in all subsequent SSE events.
    *   **SSE `run_start` Event:** Backend MUST send this first. It MUST contain `thread_id`, `runConfig`, `initialMessages`, and `node`. (The separate `thread_info` event is eliminated).
    *   **SSE Structure:** Subsequent events (`chunk`, `ai_tool_chunk`, `tool_result`, `error`, `end`) MUST include `node` in their `data` payload.
    *   **Tool Result Structure:** `tool_result` data MUST use `content` field and include `tool_call_id`.
    *   **SSE `end` Event:** MUST include final `checkpoint_id` in its `data` payload.
    *   Backend graph logic MUST derive concatenated constitution string from `runConfig` if needed.
*   **/api/threads/{thread_id}/latest Endpoint:**
    *   Accepts `thread_id`.
    *   Fetches latest checkpoint.
    *   Returns a single `HistoryEntry` object (including `checkpoint_id`, `thread_id`, `values.messages`, `runConfig`).
    *   `messages` array MUST conform to frontend `MessageType` structure (including `nodeId`).
*   **/api/threads/{thread_id}/history Endpoint:**
    *   Accepts `thread_id`.
    *   Fetches all relevant checkpoints.
    *   Returns `HistoryEntry[]`.
    *   Each `HistoryEntry` MUST conform to the structure defined for `/latest`.

## 5. Frontend Workflow Examples (Conceptual - Reflecting `ThreadCacheData`)

*   **New Session:** (Unchanged) Create `UISessionState`, add to `uiSessions`, set `activeSessionId`.
*   **Start First Run:**
    1.  Get `RunConfig`. Construct `CheckpointConfigurable` (`thread_id: null`).
    2.  Call `api.streamRun`.
    3.  On receiving `run_start`: `api.ts` initializes `threadCacheStore` entry for the new `threadId` with `ThreadCacheData` (populating `history`, setting `isStreaming: true`, `error: null`). Calls `addKnownThreadId`, `addThreadToSession`.
    4.  On receiving stream updates (`chunk`, etc.): `api.ts` retrieves `ThreadCacheData`, clones `history`, calls `streamProcessor` mutator, updates `history` in the store entry (keeping `isStreaming: true`).
    5.  On receiving `end`: `api.ts` calls `getLatestHistory` (which fetches final state and updates the store entry, setting `isStreaming: false`).
*   **Start Subsequent Run:** Similar, but `CheckpointConfigurable` uses existing `thread_id`. `api.ts` updates existing `threadCacheStore` entry.
*   **Switching Tabs:**
    1.  Update `activeSessionId`.
    2.  `ChatInterface` gets `UISessionState`, gets `threadIds`.
    3.  For each `threadId`: Check `threadCacheStore`. If `history` is null, `api.getLatestHistory(threadId)` is triggered (updates store).
    4.  Render UI using data derived from `threadCacheStore`.

## 6. Implementation Plan (Next Steps)

This section outlines the immediate tasks required to implement the refined state management approach.

**Guiding Principles Reminder:**
*   Update type definitions (`global.d.ts`, `backend_models.py`) first. (Done for this phase)
*   Implement changes step-by-step, verifying as you go.
*   Adhere strictly to commenting policy (no ephemeral/obvious comments).
*   Handle realistic errors cleanly, avoid excessive defensive coding.

**Implementation Tasks:**

1.  **Update Type Definitions (Done):**
    *   `global.d.ts`: Added `ThreadCacheData`, removed `SSEThreadInfoData` and `"thread_info"` type.
    *   `backend_models.py`: Removed `SSEThreadInfoData` model and `"thread_info"` type.

2.  **Update Stores (`src/lib/stores.ts`) (Completed):**
    *   Verified `historyCacheStore` was already renamed to `threadCacheStore`.
    *   Verified type signature is `Writable<Record<string, ThreadCacheData>>`.

3.  **Update API Layer (`src/lib/api.ts`) (Completed):**
    *   Updated store references to `threadCacheStore`.
    *   Refactored `getLatestHistory` (implicitly used by `handleEndEvent`).
    *   Refactored SSE event handlers (`handleRunStartEvent`, `handleStreamUpdateEvent`, `handleErrorEvent`, `handleEndEvent`) to work with `ThreadCacheData`, managing `isStreaming` and `error` flags.
    *   Removed `handleThreadInfoEvent` and its usage.
    *   Verified type-safe event dispatch map is used.
    *   Resolved TS errors using non-null assertion (`!`) where runtime checks guarantee non-null history.
    *   Removed unnecessary comments.

4.  **Update Stream Processor (`src/lib/streamProcessor.ts`) (Completed):**
    *   Verified mutator functions (`handleChunk`, `handleToolChunk`, `handleToolResult`) correctly accept `HistoryEntry` and modify its `values.messages` array as expected. No changes were needed.

5.  **Create `ChatView.svelte` Component (Completed):**
    *   Created `superego-frontend/src/lib/components/ChatView.svelte`.
    *   Accepts `threadId` prop.
    *   Imports `threadCacheStore`.
    *   Reactively derives `history`, `isStreaming`, `error` from the store entry.
    *   Renders messages using `MessageCard.svelte`.
    *   Displays error messages.
    *   Shows a spinner during initial load and active streaming.

6.  **Refactor `ChatInterface.svelte` Component (Completed):**
    *   Removed local history/message state management and rendering logic.
    *   Implemented responsive, paginated carousel:
        *   Uses `bind:clientWidth` to detect container width.
        *   Calculates `itemsPerPage` based on `MIN_CHAT_VIEW_WIDTH`.
        *   Renders the appropriate slice of `activeThreadIds` using `<ChatView>` components side-by-side within `.page-content`.
        *   Added pagination controls (buttons, dots) when `totalPages > 1`.
    *   Simplified `handleSend` to only call `api.streamRun`.
    *   Cleaned up unused code and styles.

7.  **Refactor Constitution Handling & Sending Logic (Completed):**
    *   **Goal:** Ensure selected constitutions are correctly used when sending messages, improving separation of concerns.
    *   **Approach:**
        *   `ConstitutionSelector.svelte` uses global/local stores, manages local selection, derives `configuredModules`, and dispatches `configChange`. (Verified Complete)
        *   Created `src/lib/services/chatService.ts` to:
            *   Store the latest `configuredModules` received via `updateChatConfig`.
            *   Provide `sendUserMessage(userInput)` function that reads stored config, builds `RunConfig`, and calls `api.streamRun`.
        *   Refactored `ChatInterface.svelte` to:
            *   Call `chatService.updateChatConfig` on `configChange` event from `ConstitutionSelector`.
    *   Call `chatService.sendUserMessage` in its `handleSend` function, removing direct API call and placeholder `RunConfig`.

7.  **Testing:** Thoroughly test the core workflows after completing the above steps. (Ongoing)

**Status:** **COMPLETED** (As of 2025-04-10 ~02:58 AM) - All implementation tasks related to this refactor plan are finished. The core chat workflow should now function correctly with the new state management and backend history loading logic.

**Next Steps (Post-Refactor):**
1.  Small Cleanups (Details TBD)
2.  Implement Comparison Mode (Details TBD)

**Future Considerations:**
*   Consider renaming `HistoryEntry` to `CheckpointState` for clarity in future work.
*   (Addressed by creating `chatService.ts`)

## 7. Refactor Log (Pruned)

*   Previous refactoring steps completed up to implementing the initial stream processing logic (`streamProcessor.ts`) and integrating it into `api.ts` using the original `historyCacheStore` and map dispatch approach. Type definitions and backend SSE structure were aligned.
*   **Next Phase:** Implement the refined caching (`ThreadCacheData`), type-safe dispatch, and UI component refactoring outlined in Section 6. (Completed Steps 1-6)
*   **Constitution Integration:** Refactored `ConstitutionSelector` to use stores and dispatch config. Created `chatService.ts` to handle config state and API calls. Updated `ChatInterface` to use the service. (Completed Step 7)

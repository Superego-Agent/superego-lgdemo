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
*   **Minimalism:** This is a refactor for a research demo app, not a production system. Features and error handling beyond the absolute minimum required for the core goal WILL be omitted. **NO extraneous error handling** will be added without explicit discussion and justification – we are not building mountains of defensive code here.
*   **No Data Migration:** Existing `localStorage` data (`superego_conversations`) will be **ignored and discarded**. Users will start with a clean slate. No time will be wasted on migration code.
*   **Strict Commenting Policy:** Comments are **ONLY** permitted if they provide permanent, essential clarification for non-obvious logic that cannot be made clearer through better naming or structure. **NO ephemeral comments, NO placeholder TODOs, NO explaining the obvious.** Adding comments requires extreme caution and justification. This is non-negotiable.
*   **Derived State:** Minimize persisted frontend state. Avoid storing data that can be derived from fetched backend checkpoints (e.g., message history, run configurations). Leverage Svelte's derived stores to compute view-specific data dynamically from the source-of-truth checkpoint data when a session is active.

## 3. Architecture Overview

### Core Concepts

*   **Checkpoints (Backend):** The backend LangGraph checkpointer is the **single source of truth**. It saves snapshots (`StateSnapshot`) of the graph state (including messages) at each step of execution.
*   **`threadId` (Backend & Frontend):** A unique identifier (e.g., UUID string) managed by the backend checkpointer, linking all checkpoints belonging to a single continuous conversation thread.
*   **`configurable` Metadata (Backend):** When invoking the backend graph, the frontend includes custom metadata within the `configurable` dictionary. This metadata is persisted with the checkpoint by the checkpointer. Key custom metadata includes:
    *   `agentRunId`: A unique frontend-generated UUID identifying a specific interaction attempt (e.g., one user message and the subsequent agent response sequence).
    *   `frontendConfig`: An object containing the specific configuration (selected constitutions, adherence levels, etc.) used by the frontend for that `agentRunId`.
*   **`UISession` (Frontend):** Represents a UI tab or view. It maps a frontend-generated `sessionId` to one or more backend `threadId`s that should be displayed within that tab. This allows for single-thread views (standard chat) and multi-thread views (compare mode).
*   **`knownThreadIds` (Frontend):** A simple list stored in `localStorage` containing all `threadId`s that this specific client/browser has created or interacted with. Acts as a client-side index to filter relevant sessions/threads.

### Data Structures (Interfaces - in `global.d.ts`)

```typescript
// --- Core Frontend State ---

/** Represents a single UI tab/view state stored in localStorage */
interface UISessionState {
    sessionId: string; // Frontend-generated UUID v4 (identifies the UI tab)
    name: string;      // User-editable name for the session/tab
    createdAt: string; // ISO timestamp string
    lastUpdatedAt: string; // ISO timestamp string
    threadIds: string[]; // List of LangGraph backend thread IDs displayed in this session
}

// --- Constitution Representation ---

/**
 * Represents a constitution module configured with an adherence level for use.
 * Used in frontend state and sent to/received from the backend.
 */
interface ConfiguredConstitutionModule {
    /** Unique identifier (global ID or frontend-generated for local). */
    id: string;
    /** Title of the module. */
    title: string;
    /** Adherence level (1-5). */
    adherence_level: number;
    /** Full text of the module (optional; if missing, backend fetches using ID). */
    text?: string;
}

// --- API Request Payloads ---

/** Represents the configuration for a specific agent run attempt. */
interface RunConfig {
    /** Array of constitution modules configured for this run. */
    configuredModules: ConfiguredModule[];
    // Potentially other run-specific parameters...
}

/**
 * Represents the structure of the 'configurable' object passed TO the backend API
 * and persisted within the checkpoint's config field.
 */
interface CheckpointConfigurable {
    thread_id: string | null; // LangGraph thread ID (null for new thread)
    runConfig: RunConfig;     // The config used for this run (defined above)
    // Other potential custom keys...
}

// --- API Response Payloads ---

/**
 * Represents the data structure returned by backend endpoints fetching checkpoint data
 * (e.g., /api/threads/{thread_id}/history, /api/threads/{thread_id}/latest).
 * Messages directly use the aligned frontend MessageType.
 */
interface HistoryEntry {
    checkpoint_id: string; // Unique ID of the checkpoint
    thread_id: string;     // ID of the conversation thread
    values: {
        /** Message history up to this point, using the aligned MessageType[]. */
        messages: MessageType[]; // Assumes MessageType is aligned with backend structure
    };
    runConfig: RunConfig; // Configuration used for the run leading to this state
}

// --- Message Representation ---

/**
 * Represents the different types of messages in the application.
 * IMPORTANT: This definition in `global.d.ts` MUST be modified to align closely
 * with the structure of serialized LangChain messages stored in backend checkpoints
 * (e.g., using `type` instead of `sender`, adjusting tool call structure).
 * Example (Conceptual - requires verification against backend):
 *
 * interface BaseApiMessage {
 *   type: 'human' | 'ai' | 'system' | 'tool';
 *   content: string | any;
 *   name?: string; // For tool messages or AI messages
 *   tool_call_id?: string; // For tool messages
 *   // For AI messages:
 *   tool_calls?: Array<{ id: string; name: string; args: Record<string, any>; }>;
 *   invalid_tool_calls?: any[];
 *   additional_kwargs?: Record<string, any>;
 * }
 * // Define HumanApiMessage, AiApiMessage, ToolApiMessage, SystemApiMessage extending BaseApiMessage
 * type MessageType = HumanApiMessage | AiApiMessage | ToolApiMessage | SystemApiMessage;
 */
// Existing MessageType definition in global.d.ts needs modification.

```

### Frontend State (`localStorage`)

```typescript
// Using 'svelte-persisted-store' for automatic localStorage synchronization.
import { persisted } from 'svelte-persisted-store';
import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';

/**
 * List of all LangGraph thread IDs known to this client. Acts as an index.
 * Synced with localStorage key 'superego_knownThreads'.
 */
export const knownThreadIds = persisted<string[]>('superego_knownThreads', []);

/**
 * Holds state for ALL UI sessions/tabs, keyed by sessionId.
 * Maps UI tabs to backend thread IDs.
 * Synced with localStorage key 'superego_uiSessions'.
 */
export const uiSessions = persisted<Record<string, UISessionState>>('superego_uiSessions', {});

/**
 * Tracks the sessionId of the currently viewed session/tab (NOT persisted).
 */
export const activeSessionId: Writable<string | null> = writable(null);
```

### Backend State (Checkpointer)

*   The backend utilizes a LangGraph checkpointer (e.g., `AsyncSqliteSaver`) configured to persist graph state.
*   Checkpoints store the graph state (`values`, including messages), internal execution `metadata`, and the `configurable` dictionary passed during invocation (containing `thread_id`, `agentRunId`, `frontendConfig`).
*   Checkpoints are grouped by `threadId`.

## 4. Backend API Requirements

*   **/api/runs/stream Endpoint:**
    *   **MUST** accept a request body containing `input` (user message) and `configurable` (type `CheckpointConfigurable`).
    *   The `configurable` object **MUST** contain:
        *   `thread_id: string | null`: The target conversation thread. If `null`, the backend MUST generate a new `threadId`.
        *   `runConfig: RunConfig`: The configuration object provided by the frontend for this run.
    *   The backend **MUST** pass this entire `configurable` object when invoking the LangGraph graph (`.stream()` or `.invoke()`) so it gets persisted with the checkpoint.
    *   The backend **MUST** return the generated or provided `threadId` in SSE events (e.g., in a `thread_info` event or within each event's metadata).
    *   The backend **MUST** return the final `checkpoint_id` of the run in the `end` SSE event (useful for identifying the final state).
    *   The backend graph logic **MUST** be responsible for deriving the final concatenated constitution string from the `runConfig.configuredModules` array at runtime if needed (e.g., for system prompts).
*   **/api/threads/{thread_id}/latest Endpoint:**
    *   **MUST** accept a `thread_id` (string UUID).
    *   **MUST** fetch the latest checkpoint for the given `thread_id`.
    *   **MUST** return a single `HistoryEntry` object.
    *   The returned `HistoryEntry` **MUST** include:
        *   `checkpoint_id`: The ID of the latest checkpoint.
        *   `thread_id`: The ID of the thread.
        *   `values`: Containing `messages` (the full message list up to this checkpoint).
        *   `runConfig`: Extracted from the checkpoint's `config.configurable.runConfig`.
    *   The `messages` array within `values` **MUST** conform to the frontend's `MessageType` structure (i.e., backend performs necessary mapping/adaptation from raw checkpoint message format).
*   **/api/threads/{thread_id}/history Endpoint:**
    *   **MUST** accept a `thread_id` (string UUID).
    *   **MUST** fetch all relevant checkpoints for the given `thread_id`, ordered chronologically.
    *   **MUST** return a list of `HistoryEntry` objects (`HistoryEntry[]`).
    *   Each returned `HistoryEntry` **MUST** conform to the structure defined for the `/latest` endpoint (containing `checkpoint_id`, `thread_id`, `values.messages`, `runConfig`, with messages adapted to `MessageType`).

## 5. Frontend Workflow Examples

*   **New Session:**
    1.  User clicks "New Session".
    2.  `sessionManager.createNewSession` creates a `UISessionState` with a unique `sessionId` and `threadIds: []`.
    3.  Adds the new session to `uiSessions`.
    4.  Sets `activeSessionId`. (UI updates to show empty state).
*   **Start First Run (Sending First Message in a New Session):**
    1.  `ChatInterface` gets the active `UISessionState` (which has `threadIds: []`).
    2.  Get `RunConfig` (selected `configuredModules`).
    3.  Construct `CheckpointConfigurable` payload with `thread_id: null` and the `runConfig`.
    4.  Call backend `/api/runs/stream` API with the payload.
    5.  Backend generates a new `threadId`, runs graph, saves checkpoints.
    6.  On receiving the `thread_info` SSE event (or similar event containing the new `threadId`):
        *   Add the new `threadId` to the `knownThreadIds` store.
        *   Update the current `UISessionState` in `uiSessions` to include the new `threadId` in its `threadIds` list.
    7.  On receiving the `end` SSE event (containing the final `checkpoint_id`):
        *   Optionally trigger a fetch to `/api/threads/{new_threadId}/latest` to get the final `HistoryEntry` (though optimistic updates from SSE chunks might suffice).
        *   UI displays the messages received via SSE.
*   **Start Subsequent Run (Single Thread Session):**
    1.  `ChatInterface` gets active `UISessionState` (has one `threadId`).
    2.  Get `RunConfig` (selected `configuredModules`).
    3.  Construct `CheckpointConfigurable` payload with the existing `thread_id` and the `runConfig`.
    4.  Call backend `/api/runs/stream` API with the payload.
    5.  Backend continues the thread, saves new checkpoints.
    6.  UI updates based on SSE events. On `end` event, optionally fetch `/latest` for final state confirmation.
*   **Start Run (Compare Mode Session - Conceptual):**
    *   *Assumption:* Compare mode runs each configuration on a **separate `threadId`**.
    1.  `ChatInterface` gets active `UISessionState` (has multiple `threadIds`, e.g., `threadId_A`, `threadId_B`).
    2.  Get `RunConfig` for leg A (`runConfig_A`) and leg B (`runConfig_B`).
    3.  Construct `CheckpointConfigurable` payload A (`thread_id: threadId_A`, `runConfig: runConfig_A`).
    4.  Construct `CheckpointConfigurable` payload B (`thread_id: threadId_B`, `runConfig: runConfig_B`).
    5.  Call backend `/api/runs/stream` API with payload A.
    6.  Call backend `/api/runs/stream` API with payload B.
    7.  UI handles two independent SSE streams, routing updates to the correct display column based on the `threadId` received in events.
    8.  On `end` events, optionally fetch `/latest` for each thread.
*   **Receive SSE Event:**
    1.  Events **MUST** contain `threadId`.
    2.  Frontend routes event data based on `threadId` to update the relevant part of the UI (e.g., specific message list in single view or specific column in compare view).
    3.  UI updates optimistically based on message chunks.
*   **Switching Tabs (Activating a Session):**
    1.  User clicks a session in the sidebar.
    2.  Update `activeSessionId` store.
    3.  `ChatInterface` (or relevant component) reacts to `activeSessionId` change:
        *   Gets the corresponding `UISessionState` from `uiSessions`.
        *   Gets the `threadIds` from the session state.
        *   If `threadIds` exist:
            *   For each `threadId`, call backend `/api/threads/{thread_id}/latest` endpoint.
            *   Store the received `HistoryEntry` objects temporarily (e.g., in a non-persisted store or component state).
            *   Render the message history view(s) using the `messages` array from the fetched `HistoryEntry`(s). Display `runConfig` details as needed.
        *   If `threadIds` is empty, display an empty chat state.

## 6. Implementation Notes (High-Level)

*   **Interfaces (`src/global.d.ts`):**
    *   Define `UISessionState`, `ConfiguredModule`, `RunConfig`, `CheckpointConfigurable`, `HistoryEntry`.
    *   **CRITICAL:** Modify the existing `MessageType` union (and constituent interfaces like `HumanMessage`, `AIMessage`, etc.) to align with the backend's serialized message structure (e.g., use `type` instead of `sender`, expect top-level `tool_calls`, remove frontend-only fields like `id`, `timestamp`).
*   **Libraries:** Use `svelte-persisted-store` for `uiSessions` and `knownThreadIds`. Use `uuid` for generating `sessionId`.
*   **Stores (`src/lib/stores.ts`):**
    *   Implement `uiSessions`, `activeSessionId`, `knownThreadIds` using `svelte-persisted-store`.
    *   Remove old stores related to `conversationStates`, `activeConstitutionIds`, `constitutionAdherenceLevels`, etc.
    *   Consider a non-persisted store to hold the fetched `HistoryEntry[]` for the active session.
*   **State Management Functions (`src/lib/sessionManager.ts` or similar):**
    *   Create functions for managing `uiSessions` (create, rename, delete, update `threadIds`).
    *   Create functions for managing `knownThreadIds`.
    *   Remove old `conversationManager.ts`.
*   **UI Components:**
    *   `Sidebar`: List sessions from `uiSessions`. Handle creation of new `UISessionState` entries. Set `activeSessionId` on selection.
    *   `ChatInterface` / `CompareInterface`:
        *   React to `activeSessionId` changes.
        *   Fetch `HistoryEntry` data from `/api/threads/{thread_id}/latest` for the active `threadIds`.
        *   Render messages directly using the `messages` array (now aligned `MessageType[]`) from the fetched `HistoryEntry`(s).
        *   Display `runConfig` details (e.g., applied constitutions) from the fetched `HistoryEntry`(s).
        *   Handle message sending (`handleSend`) by constructing the `CheckpointConfigurable` payload (with `RunConfig`) and calling the `/api/runs/stream` API.
        *   Handle SSE events, routing based on `threadId`.
    *   `ConstitutionSelector`, etc.: Provide data needed to construct the `RunConfig` (specifically the `configuredModules: ConfiguredModule[]`).
*   **API Calls (`src/lib/api.ts`):**
    *   Update `streamRun` function to construct and send the `CheckpointConfigurable` payload.
    *   Implement `getLatestHistory(threadId)` function to call `/api/threads/{thread_id}/latest` and return a typed `HistoryEntry`.
    *   Implement `getFullHistory(threadId)` function to call `/api/threads/{thread_id}/history` and return typed `HistoryEntry[]`.
    *   Remove message transformation logic from API fetching functions.
    *   Update SSE handling logic to route based on `threadId`.
*   **Testing:** Focus on core workflows: creating sessions, sending messages (first and subsequent), fetching/displaying latest state via `/latest`, persistence across reloads, switching sessions. Verify compare mode structure using separate `threadId`s.

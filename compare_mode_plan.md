# Plan: Implement Compare Mode Feature (Draft)

**Note:** This plan is based on analysis of the existing codebase and discussions.

## 1. Goal
Allow users to define multiple agent configurations (e.g., "Superego A", "Superego B") within a single UI session, run them concurrently with the same input, and view the results side-by-side.

## 2. State Management
- **Structure:** Utilize the existing `UISessionState` and `ThreadConfigState` interfaces provided initially.
  - `UISessionState`: Represents the state of a single UI tab/session.
  - `UISessionState.threads` (`Record<string, ThreadConfigState>`): Stores the multiple configurations (Superego A, B, etc.), keyed by a frontend-generated UUID (`configThreadId`). This `configThreadId` **is** the persistent backend LangGraph `thread_id`.
  - `UISessionState.activeConfigThreadId`: Tracks which configuration card is currently selected for editing.
  - **Remove/Ignore:** `UISessionState.threadIds` array is not needed for compare mode; derive displayed threads from `Object.keys(UISessionState.threads)`.
- **Stores:** Continue using `$uiSessions`, `$activeSessionId`, `$threadCacheStore`.

## 3. UI Components
- **Rename:** Rename `RunConfigurationPanel.svelte` to `RunConfigurationBox.svelte`.
- **New Components:**
  - `RunConfigManager.svelte`: Displays the configuration cards. Placed inside `RunConfigurationBox.svelte`.
  - `ConfigCard.svelte`: Displays a single configuration card (name, constitution chips - chips deferred initially). Rendered by `RunConfigManager`.
- **Placement:** `RunConfigManager` sits within `RunConfigurationBox`, likely above the existing constitution sliders/controls.
- **Binding:**
  - Controls within `RunConfigurationBox` (sliders, etc.) bind directly to properties within the active configuration object accessed via the main store subscription (e.g., `$uiSessions[$activeSessionId].threads[$activeConfigThreadId].runConfig.someProperty`). Svelte's `bind:` handles reactivity.
  - Clicking a `ConfigCard` updates `$uiSessions[$activeSessionId].activeConfigThreadId`.
- **Display:**
    - Modify `ChatInterface.svelte` (lines 26, 37) to derive `activeThreadIds` (and thus `paginatedThreadIds`) from `Object.keys(currentSessionState.threads)` instead of `currentSessionState.threadIds`.
    - Existing pagination and `ChatView` rendering logic should then work correctly with the list of configuration thread IDs.

## 4. Concurrency & Run Logic
- **Initiation:** Modify the `sendUserMessage` function in `src/lib/services/chatService.ts`.
- **Filtering:** Identify configurations in the current session's `threads` object where `isEnabled` is true.
- **Iteration:** Loop through these *enabled* configurations.
- **API Calls:** For each enabled configuration, call the existing `api.ts::streamRun` function sequentially from the frontend, passing the configuration's key as the `threadId` and its `runConfig`.
- **Thread Handling:** Uses **Option 1 (Continue Threads)** by default, as `streamRun` is called with the persistent `threadId` associated with the configuration.
- **Backend:** Assumes backend handles these sequential requests concurrently using async processing and correctly continues threads based on the provided `thread_id`.
- **SSE:** **Verified:** Backend (`api_routers/runs.py`) consistently includes `thread_id` in all relevant SSE events. Existing SSE handler in `api.ts` will correctly route events.

## 5. Backend Changes
- None required *for enabling concurrency* or SSE handling based on this plan.

## 6. Next Steps
- Plan finalized after analysis.
- Request switch to 'code' mode for implementation.
# Integrated Rune Refactoring & Structure Standardization Plan

**Goal:** Refactor frontend state management to use Svelte 5 Runes following the established class-based instance pattern, while simultaneously standardizing the file structure by separating state logic (`src/lib/state/`) and API interaction logic (`src/lib/api/`).

**Pattern:** Utilize exported class instances containing `$state` properties and mutation methods. State modules reside in `src/lib/state/` and API modules in `src/lib/api/`. Persistence is handled via the `persistedLocalState` utility where needed.

---

## Phased Implementation Plan

**Phase 0: Prepare Standardized Directories**
1.  Create `superego-frontend/src/lib/state/`.
2.  Create `superego-frontend/src/lib/api/`.

**Phase 1: Refactor Stream State & SSE API Logic**
1.  **Move & Refine State:** Move `AppStateStore` class from `stores.svelte` to `src/lib/state/app.svelte`. Export `appState` instance. Update imports.
2.  **Move & Refine SSE Logic:** Move SSE handling logic from `sseService.ts` to `src/lib/api/sse.svelte`. Ensure it uses `appState` from `state/app.svelte`. Update imports.
3.  **Deprecate:** Deprecate/delete `sseService.ts` and `streamProcessor.ts`. Remove `AppStateStore` definition from `stores.svelte`.

    *   **Note:** Imports within `chatService.ts` were updated to point to new locations, but the file itself (`chatService.ts`) was not renamed or refactored to use Runes in this phase. This can be addressed in a subsequent refactoring phase if desired.
**Phase 2: Refactor Session State & Related API Logic**
1.  **Create State Class:** Create `src/lib/state/session.svelte` with `SessionStateStore` class.
2.  **Handle Persistence:** Use `persistedLocalState` when exporting the `sessionState` instance.
3.  **Move & Refine Session API Logic:** Move relevant REST calls to `src/lib/api/rest.svelte` (or `api/session.svelte`). Ensure `SessionStateStore` methods call these. Update imports.
4.  **Refactor Consumers:** Update components/services to use `sessionState` from `state/session.svelte` and API functions from `src/lib/api/`.
5.  **Deprecate:** Remove old persisted exports (`persistedUiSessions`, etc.) from `stores.svelte`. Deprecate/delete `sessionManager.ts`.

**Phase 3: Refactor UI State**
1.  **Move State Class:** Move `UIStateStore` class from `stores/uiState.svelte` to `src/lib/state/ui.svelte`. Export `uiState` instance. Update imports.
2.  **Deprecate:** Delete `stores/uiState.svelte`.

**Phase 4: Refactor General API Logic** (Optional but recommended)
1.  **Consolidate REST:** Move remaining general REST API calls from `api.ts` to `src/lib/api/rest.svelte`.
2.  **Deprecate:** Deprecate/delete `api.ts` if empty.

**Phase 5: Refactor Component Consumers**
1.  Thoroughly review components (esp. `RunConfigurationPanel.svelte`, `Sidebar.svelte`, `ChatInterface.svelte`) ensuring they import from `src/lib/state/` and `src/lib/api/`.

**Phase 6: Testing**
1.  Write/update unit tests for methods on state store classes (`AppStateStore`, `SessionStateStore`, `UIStateStore`).

**Phase 7: Documentation**
1.  Update `superego-frontend/CODING_GUIDELINES.md` with the standardized structure and class-based Rune pattern.

**Phase 8: Cleanup `stores.svelte`**
1.  Ensure `stores.svelte` is empty or only contains necessary re-exports (ideally empty). Remove the file if possible.

---

## Conceptual Flow Diagram

```mermaid
graph TD
    subgraph Frontend Components
        direction LR
        CompA[...]
        CompB[RunConfigurationPanel]
        CompC[...]
    end

    subgraph State Modules (src/lib/state/)
        direction LR
        SessionState[session.svelte <br> (SessionStateStore)]
        AppState[app.svelte <br> (AppStateStore)]
        UiState[ui.svelte <br> (UIStateStore)]
        %% Potentially others like theme.svelte if refactored
    end

    subgraph API Modules (src/lib/api/)
        direction LR
        SseApi[sse.svelte]
        RestApi[rest.svelte]
        %% Potentially others like session.svelte
    end

    subgraph Utils / Persistence
        PersistedUtil[persistedLocalState.svelte]
        LocalStorage[(LocalStorage)]
    end

    %% Component Dependencies
    CompA --> SessionState
    CompB --> SessionState
    CompB --> UiState
    CompC --> AppState

    %% State Dependencies
    SessionState -- Wrapped by --> PersistedUtil
    PersistedUtil --> LocalStorage
    %% AppState & UiState are not persisted via this util in current code

    %% API Dependencies
    SseApi -- Calls methods on --> AppState
    SessionState -- Calls functions in --> RestApi %% Methods in SessionStateStore call API
    CompA -- Calls functions in --> RestApi %% e.g., fetching constitutions

    %% Service Dependencies
    %% SseApi might call RestApi if needed for setup
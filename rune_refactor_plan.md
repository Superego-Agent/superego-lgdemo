# Frontend State Management Refactoring Plan (Svelte 5 Runes)

**Overarching Goal:** Refactor state management in identified areas (`RunConfigurationPanel`, `sseService`, `streamProcessor`, `sessionManager`) to use Svelte 5 Runes, improving context isolation, testability, and code clarity, while aligning with modern Svelte practices and reducing cognitive load.

**Core Pattern:** Utilize `.svelte.ts` modules within a dedicated `src/lib/state/` directory to encapsulate reactive state (`$state`), derived values (`$derived`), mutation functions, and related side effects (`$effect`).

**Detailed Steps:**

1.  **Establish Directory Structure:**
    *   Ensure `src/lib/state/` exists for Rune-based state modules.
    *   Ensure API interaction logic is separated (e.g., in `src/lib/api/` or `src/lib/services/`).

2.  **Create State Logic Modules (`.svelte.ts`):**
    *   Create modules within `src/lib/state/` corresponding to the complex state domains identified:
        *   `state/session.svelte.ts`: Manages session, thread, and run configuration state (replacing logic tied to `$uiSessions`).
        *   `state/stream.svelte.ts`: Manages stream history and cache state (replacing logic tied to `$threadCacheStore`).
    *   **Implementation within modules:**
        *   Define core reactive state variables using `$state`.
        *   Define computed/derived values using `$derived` as needed.
        *   Define and export functions that directly mutate the `$state` variables to handle updates.
        *   Use `$effect` to manage side effects related to state changes (e.g., persistence, logging), ensuring browser checks (`import { browser }`) guard client-side-only effects.

3.  **Refactor `sessionManager.ts`:**
    *   Migrate the state management logic related to sessions/threads/configs from `sessionManager.ts` (and the `$uiSessions` store it likely manages) into `state/session.svelte.ts`.
    *   Update functions previously in `sessionManager.ts` (or components that called them) to import and use the new mutation functions and reactive state from `state/session.svelte.ts`.
    *   Simplify or potentially remove `sessionManager.ts` if its primary role was managing the old store structure.

4.  **Refactor `streamProcessor.ts` & `sseService.ts`:**
    *   Migrate the state management logic related to stream history/cache (likely involving `$threadCacheStore`) from `sseService.ts` and `streamProcessor.ts` into `state/stream.svelte.ts`.
    *   Rewrite the state update logic using direct `$state` mutation within exported functions in `state/stream.svelte.ts`.
    *   Refactor `sseService.ts` event handlers (`handleRunStartEvent`, `handleStreamUpdateEvent`, etc.) to call the mutation functions from `state/stream.svelte.ts` instead of performing complex updates or calling mutating functions from `streamProcessor.ts`.
    *   Simplify or potentially remove `streamProcessor.ts`.

5.  **Refactor `RunConfigurationPanel.svelte`:**
    *   Remove the direct state manipulation logic (e.g., `getModule`, `handleCheckboxChange`, `handleSliderInput`, `updateModules`).
    *   Import the necessary reactive state (or getters) and mutation functions (e.g., `toggleModule`, `setAdherenceLevel`) from `state/session.svelte.ts`.
    *   Update the component's template to read reactive state directly.
    *   Update event handlers to call the imported mutation functions.

6.  **Testing:**
    *   Write unit tests for the exported mutation functions within the `.svelte.ts` state modules (`state/session.svelte.ts`, `state/stream.svelte.ts`) to verify correct state transitions.

7.  **Document Pattern:**
    *   Update `superego-frontend/CODING_GUIDELINES.md`.
    *   Add a section explaining the preferred Rune-based state management pattern: using `.svelte.ts` modules in `src/lib/state/` with `$state`, `$derived`, `$effect`, and exported mutation functions. Include a concise code example illustrating the pattern.
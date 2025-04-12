# Frontend Coding Guidelines & Refactoring Principles

This document outlines the best practices and principles to follow during the frontend codebase cleanup and refactoring.

## 1. Code Quality & Refactoring Goals

*   **Eliminate Redundancy:** Replace repetitive logic (e.g., long `if/else if` chains) with cleaner structures like maps, dictionaries, or helper functions.
*   **Simplify Complexity:** Refactor deeply nested structures, complex conditionals, and convoluted logic for better readability and maintainability. Aim for elegant, functional solutions.
*   **Improve Error Handling:** Ensure error handling is robust but not overly clunky or verbose.
*   **Remove Dead Code:** Identify and remove any unused variables, functions, or components.
*   **No Band-Aid Fixes:** Prioritize robust, well-engineered solutions over quick hacks. Think about future maintainability and scalability.

## 2. Modularity & File Structure

*   **Single Responsibility:** Keep components and modules focused on a single, clear concern.
*   **Standard Directories:**
    *   State management logic resides in `src/lib/state/`, organized by domain (e.g., `threads.svelte`, `active.svelte`, `session.svelte`).
    *   API interaction logic resides in `src/lib/api/`, organized by domain or type (e.g., `sse.svelte`, `rest.svelte`, `session.svelte`).
    *   General utilities reside in `src/lib/utils/`.
*   **Minimize File Size:** Split large components or utility sets into smaller, more manageable files.
*   **Meaningful Naming:** Use clear, descriptive names for files, functions, and variables so their purpose is self-evident.
*   **Constants:** Extract constants into separate files if appropriate (e.g., `src/lib/constants.ts`).
## 3. State Management (Svelte 5 Runes - Class Pattern)

*   **Pattern:** Utilize Svelte 5 Runes (`$state`, `$derived`, `$effect`) within **classes** defined in `.svelte` files for managing reactive application state. Export instances of these classes.
*   **Location:** State store classes reside in `src/lib/state/`, organized by domain (e.g., `threads.svelte`, `active.svelte`, `session.svelte`).
*   **Implementation:**
    *   Define state properties within the class using `$state`.
    *   Define computed values using `$derived` properties or getters as needed.
    *   Define methods within the class to encapsulate state mutation logic.
    *   Use `$effect` within the class constructor or methods for side effects (e.g., persistence, DOM manipulation), ensuring browser checks (`import { browser }`) guard client-side-only effects.
    *   For simple persistence, the `persistedLocalState` utility (`src/lib/utils/persistedLocalState.svelte`) can wrap the exported instance (see `session.svelte`).
*   **Consumption:** Components and services should import the exported state instance (e.g., `import { activeStore } from '$lib/state/active.svelte';`) and access state properties or call methods directly on the instance (e.g., `activeStore.theme`, `activeStore.toggleTheme()`).
*   **Example (`src/lib/state/active.svelte` - Simplified):**
    ```typescript
    import { browser } from '$app/environment';

    type Theme = 'light' | 'dark';

    // Helper function (could be inside or outside class)
    function getInitialTheme(): Theme {
        // ... logic to get theme from localStorage or system preference ...
        return 'light'; // Placeholder
    }

    class ActiveStateStore {
        theme = $state<Theme>(getInitialTheme());
        globalError = $state<string | null>(null);
        // ... other state properties

        constructor() {
            // Effect to sync theme changes to localStorage and DOM
            $effect(() => {
                if (browser) {
                    console.log('Theme effect running:', this.theme); // Use this.theme
                    document.documentElement.setAttribute('data-theme', this.theme);
                    localStorage.setItem('theme', this.theme);
                }
            });
        }

        toggleTheme() {
            this.theme = this.theme === 'light' ? 'dark' : 'light';
        }

        setError(message: string | null) {
            this.globalError = message;
        }

        // ... other methods
    }

    // Export a single instance of the store
    export const activeStore = new ActiveStateStore();
    ```
## 3. TypeScript & Type Safety

*   **Centralized Types:** Define **ALL** shared types within `src/global.d.ts`. Avoid declaring shared types within individual component files.
*   **Strict Typing:** Utilize TypeScript's features to ensure type safety throughout the application.

## 4. Styling (SCSS/SASS)

*   **Leverage SASS:** Utilize SASS features like variables, nesting, and especially mixins (`@use '../styles/mixins' as *;`).
*   **Create Reusable Mixins:** Identify repeated style patterns and extract them into new mixins within `src/lib/styles/mixins.scss` (or a similar shared file) to promote consistency and reduce duplication.
*   **Clean CSS:** Remove commented-out styles and ensure CSS is well-organized.

## 5. Commenting Policy

*   **Meaningful Comments:** Comments should add lasting value and explain the *why* behind complex or non-obvious code, not just restate *what* the code does.
*   **Remove Fluff:** Delete temporary comments, commented-out code (unless explicitly needed for reference with a clear explanation), and comments that merely narrate self-explanatory code.
*   **Mark Refactor Areas:** Use comments (e.g., `// TODO: Refactor this section`) to flag areas that need significant improvement but are out of scope for the current change.

## 6. General Style

*   **Functional Programming:** Prefer pure functions and a functional style where appropriate. Avoid unnecessary OOP boilerplate.
*   **Use Libraries:** Leverage existing libraries effectively rather than reinventing the wheel.
*   **Readability:** Write clean, dense, and easy-to-understand code.

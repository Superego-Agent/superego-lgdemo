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
*   **Minimize File Size:** Split large components or utility sets into smaller, more manageable files.
*   **Meaningful Naming:** Use clear, descriptive names for files, functions, and variables so their purpose is self-evident.
*   **Constants/Helpers:** Extract large blocks of text, constants, or sets of helper functions into separate files if their purpose is clear from the filename (e.g., `src/lib/constants.ts`, `src/lib/utils/formatting.ts`).

## 3. State Management (Svelte 5 Runes)

*   **Pattern:** Utilize Svelte 5 Runes (`$state`, `$derived`, `$effect`) for managing reactive application state.
*   **Location:** Encapsulate state logic within dedicated `.svelte.ts` modules located in `src/lib/state/`, organized by state domain (e.g., `state/session.svelte.ts`, `state/theme.svelte.ts`).
*   **Implementation:**
    *   Define core reactive state variables using `$state`.
    *   Define computed values using `$derived` as needed.
    *   Define and export functions that directly mutate the `$state` variables to handle updates.
    *   Use `$effect` to manage side effects related to state changes (e.g., persistence, logging), ensuring browser checks (`import { browser }`) guard client-side-only effects.
*   **Consumption:** Components and services should import the reactive state (or getters for read-only access) and mutation functions from these state modules. Avoid complex `store.update()` logic or direct state manipulation in consumers.
*   **Example (`src/lib/state/theme.svelte.ts`):**
    ```typescript
    import { browser } from '$app/environment';

    type Theme = 'light' | 'dark';
    const defaultTheme: Theme = 'light';

    // Helper to get initial theme respecting user preference and localStorage
    function getInitialTheme(): Theme {
        if (!browser) return defaultTheme;
        const stored = localStorage.getItem('theme') as Theme | null;
        if (stored) return stored;
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    // Reactive state variable
    let currentTheme = $state<Theme>(getInitialTheme());

    // Effect to sync state changes to localStorage and DOM (using data-theme attribute)
    $effect(() => {
        if (browser) {
            document.documentElement.setAttribute('data-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
        }
    });

    // Exported function to toggle the theme
    export function toggleTheme() {
        currentTheme = currentTheme === 'light' ? 'dark' : 'light';
    }

    // Export read-only access to the state
    export const theme = {
        get value() { return currentTheme; }
    }
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

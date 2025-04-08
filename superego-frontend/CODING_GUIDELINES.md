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

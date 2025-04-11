# Superego LangGraph Project - Specific Rules

## 1. Architecture & State Management

*   LangGraph API: Treat LangGraph APIs (checkpointer, streaming) with caution. Verify behavior via code/docs before assuming functionality (e.g., `thread_id` handling - it *can* be preset).
*   Backend API Contract: Strictly adhere to the defined FastAPI request/response structures, especially the `configurable` object passed to `/api/runs/stream`.
*   Checkpoint-Centric: The backend LangGraph checkpointer (SQLite) is the *single source of truth* for conversation history and core state.
*   Frontend State (`threadCacheStore`):
    *   Use the `threadCacheStore` (`Writable<Record<string, ThreadCacheData>>`) as the primary source for *view-specific* thread state in the UI.
    *   Use the `ThreadCacheData` wrapper type (`global.d.ts`) to combine backend message data with transient UI flags (`isStreaming`, `error`). Do *not* add UI flags directly to backend message objects.
    *   Derive state reactively whenever possible. Minimize local component state.

## 2. Svelte & Frontend Practices

*   Declarative Svelte: Leverage Svelte's reactivity (`$:`, derived stores) extensively. Avoid imperative DOM manipulation or excessive local state.
*   Global Types: Types defined in `superego-frontend/src/global.d.ts` are globally available within the Svelte project; *do not* explicitly import them.
*   Component Structure: Keep components focused. Separate container logic from presentation logic where appropriate. Use utility functions (`src/lib/utils/`) or services (`src/lib/services/`) for reusable logic.
*   Svelte Comments: Use HTML comments (`<!-- -->`) within Svelte template sections (`<template>`), not JS comments (`//`, `/* */`). Use JS comments only within `<script>` tags.

## 3. Tooling & Environment

*   `apply_diff`: Ensure the `SEARCH` block *exactly* matches target lines, including whitespace/indentation. Use `read_file` to confirm content if `apply_diff` fails unexpectedly.
*   Python Environment: Be mindful of the Python version specified in `.python-version` and dependencies managed by Poetry/uv (`pyproject.toml`, `uv.lock`).
*   Node Environment: Use `npm` for frontend dependencies (`superego-frontend/package.json`).

## 4. Project Conventions

*   Memory Bank: Maintain the Memory Bank files (`memory-bank/`) diligently. Update `activeContext.md` and `progress.md` frequently. Refer to `systemPatterns.md` and `techContext.md` for established patterns. Read ALL memory bank files at the start of every session.
*   Constitution Files: Constitutions are defined in Markdown files within `data/constitutions/`.
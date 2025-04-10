# Project Brief: Superego LangGraph Agent

## 1. Core Goal

To develop a multi-agent system powered by LangGraph that incorporates a "superego" agent for input moderation based on configurable constitutions. The system allows interaction with an "inner agent" (which performs the main task) only after the superego approves the user's input.

## 2. Initial Scope (MVP - CLI Based)

*   A Python CLI application demonstrating the core flow: User Input -> Input Superego (Moderation) -> Inner Agent (Task Execution).
*   Superego uses configurable instructions and constitutions (Markdown files).
*   Superego uses a tool call named `superego_decision` with parameters `allow: boolean` (to permit/deny progression) and `content: string` (optional advice for the inner agent) to control flow.
*   The inner agent is already implemented as a pluggable subgraph, allowing different agent configurations. Initially, it performs a basic task (e.g., ReAct agent).
*   Agent outputs are streamed to the console.
*   Persistence handled by LangGraph's checkpointer mechanism.

## 3. Evolved Scope (Frontend Integration)

*   Develop a Svelte-based web frontend to interact with the LangGraph backend via a REST API.
*   Leverage the backend's checkpointing system as the source of truth for conversation history and run configurations.
*   Implement a robust frontend state management system (`refactor_plan.md`) centered around backend `threadId`s and checkpoints.
*   Enable advanced features like side-by-side comparison of agent runs with different configurations (e.g., different constitutions).
*   Manage UI sessions (tabs) locally, mapping them to backend conversation threads.

## 4. Key Requirements & Principles

*   **Modularity:** Allow swapping constitutions and selecting from various inner agent configurations/tools.
*   **Extensibility:** Design with future features in mind (e.g., output superego, CRUD for configurations, adding more inner agent variety).
*   **Checkpoint-Centric:** The backend checkpointer is the single source of truth for conversation state.
*   **Frontend as Thin Client:** Minimize frontend state, deriving views from fetched backend data.
*   **Development Style:** Lightweight, extensible, clean, minimal. Avoid excessive boilerplate or defensive error handling (focus on core research demo functionality).
*   **(See `refactor_plan.md` and `activeContext.md` for current development principles)**

## 5. Target Audience

*   Researchers/Developers exploring AI safety, constitutional AI, and multi-agent systems, needing a transparent platform for experimentation.
*   Users investigating the impact of different moderation rules (constitutions) on agent behavior.

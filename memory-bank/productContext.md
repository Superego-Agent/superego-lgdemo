# Product Context: Superego LangGraph Agent

## 1. Problem / Motivation

*   **Research Platform:** Need a transparent platform to research and experiment with Constitutional AI concepts, specifically input moderation using a dedicated "Superego" agent within a multi-agent (LangGraph) system.
*   **Investigating Moderation Impact:** Enable investigation into how different explicit rules (constitutions) affect the Superego agent's decisions and the overall flow of interaction.
*   **Extensible Framework:** Provide a base for future research, such as adding output screening capabilities or exploring different inner agent configurations.

## 2. Solution Overview

A multi-agent system built with LangGraph:
*   **Input Superego:** Intercepts user input, evaluates it against a selected constitution.
*   **Moderation Tool:** Uses the `superego_decision` tool (`allow: boolean`, `content: string`) to control flow to the inner agent.
*   **Inner Agent:** A pluggable subgraph that executes the main task if allowed by the Superego.
*   **Interaction:** Initially via CLI, later via a Svelte frontend.
*   **State Management:** Leverages LangGraph checkpoints for history and configuration tracking, supporting features like run comparison.

## 3. User Experience Goals

*   **Transparency:** The primary goal is to allow researchers/users to transparently observe the entire process, including the Superego's decision-making (as much as feasible) and the effect of different constitutions. The system serves as a tool for investigation.
*   **Experimentation:** Users should be able to easily select different constitutions and potentially inner agent configurations to experiment with their impact.
*   **Clear Feedback:** The interface (CLI or Frontend) should clearly stream outputs and indicate the flow of control (e.g., whether input was allowed or blocked, which agent is currently active).

## 4. Core Functionality (User Flow for Research)

1.  **Setup:** User selects a constitution (and potentially an inner agent configuration).
2.  **Input:** User provides a prompt.
3.  **Superego Moderation:** Input goes to the Superego. It consults its instructions/constitution and calls `superego_decision`. The details of this step should be observable if possible (e.g., logging, tracing).
4.  **Decision & Handoff:**
    *   If `allow: false`, the flow stops. The user is informed, ideally with any `content` provided by the Superego.
    *   If `allow: true`, the input (and optional `content`) proceeds to the Inner Agent.
5.  **Inner Agent Execution:** The Inner Agent processes the input. Its actions and outputs are streamed/displayed.
6.  **Observation:** The user observes the outcome, relating it back to the chosen constitution and input.
7.  **(Future):** An Output Superego might screen the Inner Agent's response before final display.
8.  **(Future - Frontend):** Sessions allow managing multiple experiments. Compare mode allows side-by-side analysis of runs with different configurations.

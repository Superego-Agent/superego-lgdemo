# superego_core.py
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Union, Literal, Optional
import atexit
import sqlite3
import traceback

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

from config import CONFIG
# constitution_manager is not directly used here anymore, content comes via config
from utils import shout_if_fails # Import the decorator

# --- Environment Check ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set.")

# --- Globals for DB Connection Management ---
db_connection : Optional[sqlite3.Connection] = None

# --- Instruction Loading ---
@shout_if_fails
def load_superego_instructions():
    file_path = CONFIG["file_paths"]["superego_instructions"]
    with open(file_path, encoding='utf-8') as f: # Specify encoding
        return f.read()

@shout_if_fails
def load_inner_agent_instructions():
    file_path = CONFIG["file_paths"]["inner_agent_instructions"]
    with open(file_path, encoding='utf-8') as f: # Specify encoding
        return f.read()

# --- Tools ---
@tool
def superego_decision(allow: bool) -> bool:
    """Make a decision on whether to allow or block the input."""
    return allow

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result."""
    try:
        # Safely evaluate mathematical expressions using numexpr or similar
        # For simplicity, using eval here, but replace with safer alternative in production
        # Make sure to restrict the available builtins and locals
        allowed_builtins = {'abs': abs, 'pow': pow, 'round': round}
        # Using a restricted global/local scope for eval
        result = eval(expression, {"__builtins__": allowed_builtins}, {})
        return f"{result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"

# --- Routing Logic ---
def should_continue_from_tools(state: MessagesState) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state['messages']; last_message = messages[-1]
    if not isinstance(last_message, ToolMessage): return END # Should not happen

    # Check the name of the tool that was called
    if last_message.name == "superego_decision":
        # If superego made a decision, route based on that
        try:
            # Attempt to parse the content as boolean more robustly
            allow_decision = str(last_message.content).strip().lower() == "true"
            return "inner_agent" if allow_decision else END
        except Exception:
             print(f"[yellow]Warning: Superego decision tool returned non-boolean parseable content: {last_message.content}[/yellow]")
             return END # Default to ending if decision is unclear
    else:
        # If another tool was called (e.g., calculator by inner_agent), continue to inner_agent
        return "inner_agent"

def should_continue_from_inner_agent(state: MessagesState) -> Union[Literal["tools"], Literal[END]]:
    last_message = state["messages"][-1]
    # If the last message is an AI message and it contains tool calls, route to tools
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"
    # Otherwise, end the turn
    else:
        return END

# --- Model Creation ---
@shout_if_fails
def create_models():
    superego_model = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG.get("streaming", True)
    ).bind_tools([superego_decision])

    inner_model = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG.get("streaming", True)
    ).bind_tools([calculator]) # Inner agent uses the calculator

    return superego_model, inner_model

# --- Graph Node Functions ---
def call_superego(state: MessagesState, config: dict, superego_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    # *** FIX: Use the correct key "constitution_content" from config ***
    constitution_content = config.get("configurable", {}).get("constitution_content", "")
    superego_instructions = load_superego_instructions()

    system_prompt = f"{superego_instructions}"
    if constitution_content:
        # Optionally add structure if multiple constitutions were combined
        if "\n\n---\n\n" in constitution_content: # Check if separator exists
             system_prompt += f"\n\n## Combined Constitution Sections\n{constitution_content}"
        else:
             system_prompt += f"\n\n## Constitution\n{constitution_content}"
    else:
        system_prompt += "\n\n## Constitution\nNo specific constitution provided for this run."


    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | superego_model
    try:
        # Pass only the user message to the superego for its initial decision/filtering
        user_message = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        if not user_message:
             # Handle case where there's no human message (e.g., resuming after tool call)
             # In this specific graph structure, superego only runs on the *first* message.
             # If resuming, it would likely go to 'tools' or 'inner_agent' first.
             # If the graph changes, this might need adjustment. Let's assume it gets a HumanMessage.
             # Returning empty might break graph flow if not handled by edges.
             # A safer bet might be to pass all messages if no single HumanMessage found at end?
             # Let's stick to the original logic for now: requires HumanMessage.
             print("[yellow]Warning: Superego node called without a trailing HumanMessage.[/yellow]")
             # Return an empty AIMessage to signify no action?
             # Or raise error? Let's return empty for now.
             return {"messages": []}


        # Pass config which might include thread_id, recursion_limit etc.
        response = chain.invoke({"messages": [user_message]}, config)
        response.name = "superego" # Assign name for clarity
        return {"messages": [response]}
    except Exception as e:
        print(f"[red]Error invoking superego model: {e}[/red]")
        # traceback.print_exc() # Uncomment for detailed debugging
        # Ensure the error message structure is a valid AIMessage
        error_msg = AIMessage(content=f"Error in superego: {e}", name="superego")
        return {"messages": [error_msg]}

def inner_agent(state: MessagesState, inner_model) -> Dict[str, List[BaseMessage]]:
    # Inner agent sees the full history leading up to it
    messages = state["messages"]
    inner_agent_instructions = load_inner_agent_instructions()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | inner_model
    try:
        response = chain.invoke({"messages": messages})
        # Langchain automatically assigns name if not specified
        return {"messages": [response]}
    except Exception as e:
        print(f"[red]Error invoking inner_agent model: {e}[/red]")
        # traceback.print_exc() # Uncomment for detailed debugging
        error_msg = AIMessage(content=f"Error in inner_agent: {e}", name="inner_agent")
        return {"messages": [error_msg]}

# --- Cleanup Function ---
def close_db_connection():
    global db_connection
    if db_connection:
        try: db_connection.close(); db_connection = None
        except Exception as e: print(f"[yellow]Warning: Error closing database connection:[/yellow] {e}")

atexit.register(close_db_connection)

# --- Workflow Creation ---
@shout_if_fails
def create_workflow(superego_model, inner_model):
    global db_connection

    # Tools available to the graph
    tools = [superego_decision, calculator]
    tool_node = ToolNode(tools)

    workflow = StateGraph(MessagesState) # Use MessagesState for history

    # Pass models to nodes using lambda functions or partial
    workflow.add_node("superego", lambda state, config: call_superego(state, config, superego_model))
    workflow.add_node("inner_agent", lambda state: inner_agent(state, inner_model))
    workflow.add_node("tools", tool_node)

    # Define the workflow edges
    workflow.add_edge(START, "superego")
    # After superego runs, its output (decision or thought) might involve calling superego_decision tool
    workflow.add_edge("superego", "tools")
    # After tools run, route based on the tool called (superego_decision?) or default to inner_agent
    workflow.add_conditional_edges(
        "tools",
        should_continue_from_tools,
        {"inner_agent": "inner_agent", END: END}
    )
    # After inner_agent runs, check if it called tools or if the turn ends
    workflow.add_conditional_edges(
        "inner_agent",
        should_continue_from_inner_agent,
        {"tools": "tools", END: END}
    )

    # Setup checkpointer
    db_path = CONFIG.get("sessions_dir", "data/sessions") + "/conversations.db"
    db_dir = os.path.dirname(db_path)
    if db_dir: os.makedirs(db_dir, exist_ok=True)

    if db_connection: close_db_connection()
    # Ensure check_same_thread=False for multi-threaded access if needed by server/async use
    db_connection = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn=db_connection)

    # Compile the graph with the checkpointer
    app = workflow.compile(checkpointer=checkpointer)

    # Ensure DB connection is closed on exit (atexit might not always fire)
    def signal_handler(sig, frame):
        print('Signal received, closing DB connection...')
        close_db_connection()
        sys.exit(0)
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return app
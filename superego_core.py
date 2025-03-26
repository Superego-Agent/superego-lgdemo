# superego-lgdemo/superego_core.py (Using Manual Connection + SqliteSaver)
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Union, Literal, Optional
import atexit # Import atexit for cleanup
import sqlite3 # Import sqlite3

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver # Import the Sync version


from config import CONFIG
try:
    from constitution_manager import constitution_manager
    constitution_manager_available = True
except ImportError:
    print("Warning: constitution_manager not found. Constitution features may be limited.")
    constitution_manager = None
    constitution_manager_available = False

# --- Environment Check ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set.")

# --- Global variable to hold the connection (for cleanup) ---
# Necessary for cleanup with this structure
db_connection : Optional[sqlite3.Connection] = None

# --- Instruction Loading ---
def load_superego_instructions():
    try:
        with open(CONFIG["file_paths"]["superego_instructions"]) as f:
            return f.read()
    except FileNotFoundError as e:
        print(f"Error: Could not load superego instructions: {e.filename}. Using empty string.")
        return ""
    except KeyError:
        print("Error: 'file_paths' or 'superego_instructions' missing in CONFIG. Using empty string.")
        return ""

def load_inner_agent_instructions():
    try:
        with open(CONFIG["file_paths"]["inner_agent_instructions"]) as f:
            return f.read()
    except FileNotFoundError as e:
        print(f"Error: Could not load inner agent instructions: {e.filename}. Using empty string.")
        return ""
    except KeyError:
        print("Error: 'file_paths' or 'inner_agent_instructions' missing in CONFIG. Using empty string.")
        return ""

# --- Tools ---
@tool
def superego_decision(allow: bool) -> bool:
    """Make a decision on whether to allow or block the input."""
    return allow

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result."""
    try:
        result = eval(expression, {"__builtins__": {}},
                          {"abs": abs, "pow": pow, "round": round})
        return f"{result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"


# --- Routing Logic ---
def should_continue_from_tools(state: MessagesState) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state['messages']
    last_message = messages[-1]
    if not isinstance(last_message, ToolMessage):
        print("Warning: Expected ToolMessage, got something else after tools node.")
        return END
    if last_message.name == "superego_decision":
        return "inner_agent" if str(last_message.content).lower() == "true" else END
    else:
        return "inner_agent"

def should_continue_from_inner_agent(state: MessagesState) -> Union[Literal["tools"], Literal[END]]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"
    else:
        return END


# --- Model Creation ---
def create_models():
    """Creates and returns models bound with their respective tools."""
    try:
        superego_model_raw = ChatAnthropic(
            model=CONFIG["model_name"],
            streaming=CONFIG.get("streaming", False)
        )
        superego_model = superego_model_raw.bind_tools([superego_decision])

        inner_model_raw = ChatAnthropic(
            model=CONFIG["model_name"],
            streaming=CONFIG.get("streaming", False)
        )
        inner_model = inner_model_raw.bind_tools([calculator])

        return superego_model, inner_model
    except Exception as e:
        print(f"Error creating Anthropic models: {e}")
        raise


# --- Graph Node Functions ---
def call_superego(state: MessagesState, config: dict, superego_model) -> Dict[str, List[BaseMessage]]:
    """Node function for the superego."""
    messages = state["messages"]
    constitution = config.get("configurable", {}).get("constitution", "")
    if not constitution:
        print("Warning: No constitution string found in config['configurable']['constitution'] for superego node.")
    superego_instructions = load_superego_instructions()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", f"{superego_instructions}\n\n## Constitution\n{constitution}"),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | superego_model
    try:
        response = chain.invoke({"messages": messages})
        return {"messages": [response]}
    except Exception as e:
        print(f"Error invoking superego model: {e}")
        error_msg = AIMessage(content=f"Error in superego: {e}", name="superego")
        return {"messages": [error_msg]}

def inner_agent(state: MessagesState, inner_model) -> Dict[str, List[BaseMessage]]:
    """Node function for the inner agent."""
    messages = state["messages"]
    inner_agent_instructions = load_inner_agent_instructions()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | inner_model
    try:
        response = chain.invoke({"messages": messages})
        return {"messages": [response]}
    except Exception as e:
        print(f"Error invoking inner_agent model: {e}")
        error_msg = AIMessage(content=f"Error in inner_agent: {e}", name="inner_agent")
        return {"messages": [error_msg]}


# --- Cleanup Function ---
def close_db_connection():
    """Closes the global database connection if it's open."""
    global db_connection
    if db_connection:
        print("\nClosing database connection...")
        try:
            db_connection.close()
            db_connection = None
            print("Database connection closed.")
        except Exception as e:
            print(f"Error closing database connection: {e}") # Add error handling

# Register the cleanup function to be called on exit
atexit.register(close_db_connection)

# --- Workflow Creation ---
def create_workflow(superego_model, inner_model):
    """Creates the LangGraph workflow with SqliteSaver checkpointing."""
    global db_connection # Access the global variable

    tools = [superego_decision, calculator]
    tool_node = ToolNode(tools)

    workflow = StateGraph(MessagesState)

    workflow.add_node("superego", lambda state, config: call_superego(state, config, superego_model))
    workflow.add_node("inner_agent", lambda state: inner_agent(state, inner_model))
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "superego")
    workflow.add_edge("superego", "tools")

    workflow.add_conditional_edges(
        "tools",
        should_continue_from_tools,
        {"inner_agent": "inner_agent", END: END}
    )
    workflow.add_conditional_edges(
        "inner_agent",
        should_continue_from_inner_agent,
        {"tools": "tools", END: END}
    )
    # --- End of graph definition ---

    db_path = "data/conversations.db"
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    try:
        if db_connection:
             close_db_connection()
        db_connection = sqlite3.connect(db_path, check_same_thread=False)
        print(f"Database connection established: {db_path}") # Debug print

        checkpointer = SqliteSaver(conn=db_connection)
        print("SqliteSaver instantiated with connection.") # Debug print

    except sqlite3.Error as e:
        print(f"[bold red]Fatal Error: Failed to connect to or setup SQLite database:[/bold red] {e}")
        raise # Re-raise the exception to halt execution

    # --- Compile the graph ---
    try:
        app = workflow.compile(checkpointer=checkpointer)
        print("Workflow compiled successfully with checkpointer.")
    except Exception as e:
        print(f"[bold red]Fatal Error: Failed to compile workflow:[/bold red] {e}")
        close_db_connection()
        raise 
    return app
# superego_core.py (Refactored)
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
from constitution_manager import constitution_manager # Fail loud if missing
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
    with open(file_path) as f:
        return f.read()

@shout_if_fails
def load_inner_agent_instructions():
    file_path = CONFIG["file_paths"]["inner_agent_instructions"]
    with open(file_path) as f:
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
        result = eval(expression, {"__builtins__": {}},
                          {"abs": abs, "pow": pow, "round": round})
        return f"{result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"

# --- Routing Logic ---
def should_continue_from_tools(state: MessagesState) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state['messages']; last_message = messages[-1]
    if not isinstance(last_message, ToolMessage): return END
    if last_message.name == "superego_decision": return "inner_agent" if str(last_message.content).lower() == "true" else END
    else: return "inner_agent"

def should_continue_from_inner_agent(state: MessagesState) -> Union[Literal["tools"], Literal[END]]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None): return "tools"
    else: return END

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
    ).bind_tools([calculator])

    return superego_model, inner_model

# --- Graph Node Functions ---
def call_superego(state: MessagesState, config: dict, superego_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    constitution = config.get("configurable", {}).get("constitution", "")
    superego_instructions = load_superego_instructions() # Decorated call
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", f"{superego_instructions}\n\n## Constitution\n{constitution}"),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | superego_model
    try:
        response = chain.invoke({"messages": messages})
        return {"messages": [response]}
    except Exception as e: # Keep for runtime API errors
        print(f"Error invoking superego model: {e}")
        error_msg = AIMessage(content=f"Error in superego: {e}", name="superego")
        return {"messages": [error_msg]}

def inner_agent(state: MessagesState, inner_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    inner_agent_instructions = load_inner_agent_instructions() # Decorated call
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | inner_model
    try:
        response = chain.invoke({"messages": messages})
        return {"messages": [response]}
    except Exception as e: # Keep for runtime API errors
        print(f"Error invoking inner_agent model: {e}")
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
@shout_if_fails # Decorator handles setup errors (DB conn, compile)
def create_workflow(superego_model, inner_model):
    global db_connection

    tools = [superego_decision, calculator]
    tool_node = ToolNode(tools)

    workflow = StateGraph(MessagesState)
    workflow.add_node("superego", lambda state, config: call_superego(state, config, superego_model))
    workflow.add_node("inner_agent", lambda state: inner_agent(state, inner_model))
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "superego")
    workflow.add_edge("superego", "tools")
    workflow.add_conditional_edges("tools", should_continue_from_tools, {"inner_agent": "inner_agent", END: END})
    workflow.add_conditional_edges("inner_agent", should_continue_from_inner_agent, {"tools": "tools", END: END})

    db_path = "data/conversations.db"; db_dir = os.path.dirname(db_path)
    if db_dir: os.makedirs(db_dir, exist_ok=True)

    if db_connection: close_db_connection()
    db_connection = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn=db_connection)
    app = workflow.compile(checkpointer=checkpointer)

    return app
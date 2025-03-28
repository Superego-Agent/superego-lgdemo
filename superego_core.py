import os
import sqlite3
import signal
import sys
from typing import Dict, List, Any, Union, Literal, Optional, Tuple, Annotated

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver

from config import CONFIG
from utils import shout_if_fails

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set.")

@shout_if_fails
def load_superego_instructions():
    file_path = CONFIG["file_paths"]["superego_instructions"]
    with open(file_path, encoding='utf-8') as f:
        return f.read()

@shout_if_fails
def load_inner_agent_instructions():
    file_path = CONFIG["file_paths"]["inner_agent_instructions"]
    with open(file_path, encoding='utf-8') as f:
        return f.read()

@tool
def superego_decision(allow: bool) -> bool:
    """Make a decision on whether to allow or block the input."""
    return allow

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result."""
    allowed_builtins = {'abs': abs, 'pow': pow, 'round': round}
    # Simplified: Let eval raise errors directly in this demo context
    result = eval(expression, {"__builtins__": allowed_builtins}, {})
    return f"{result}"

def should_continue_from_tools(state: MessagesState) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state['messages']; last_message = messages[-1]
    if not isinstance(last_message, ToolMessage): return END

    if last_message.name == "superego_decision":
        try:
            allow_decision = str(last_message.content).strip().lower() == "true"
            return "inner_agent" if allow_decision else END
        except Exception:
             print(f"[yellow]Warning: Superego decision tool returned non-boolean parseable content: {last_message.content}[/yellow]")
             return END
    else:
        return "inner_agent"

def should_continue_from_inner_agent(state: MessagesState) -> Union[Literal["tools"], Literal[END]]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tools"
    else:
        return END

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

def call_superego(state: MessagesState, config: dict, superego_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    constitution_content = config.get("configurable", {}).get("constitution_content", "")
    superego_instructions = load_superego_instructions()

    system_prompt = f"{superego_instructions}"
    if constitution_content:
        prompt_header = "## Combined Constitution Sections" if "\n\n---\n\n" in constitution_content else "## Constitution"
        system_prompt += f"\n\n{prompt_header}\n{constitution_content}"
    else:
        system_prompt += "\n\n## Constitution\nNo specific constitution provided for this run."

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | superego_model

    user_message = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    if not user_message:
         print("[yellow]Warning: Superego node called without a trailing HumanMessage.[/yellow]")
         return {"messages": []}

    response = chain.invoke({"messages": [user_message]}, config)
    response.name = "superego"
    return {"messages": [response]}

def inner_agent(state: MessagesState, inner_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    inner_agent_instructions = load_inner_agent_instructions()
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | inner_model
    response = chain.invoke({"messages": messages})
    return {"messages": [response]}

@shout_if_fails
def create_workflow(superego_model, inner_model) -> Tuple[Annotated[Any, "CompiledGraph"], SqliteSaver]:
    """Creates the graph, checkpointer, and returns the compiled app and checkpointer instance."""
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

    db_path = CONFIG.get("sessions_dir", "data/sessions") + "/conversations.db"
    db_dir = os.path.dirname(db_path)
    if db_dir: os.makedirs(db_dir, exist_ok=True)

    # Create the connection explicitly. It must persist.
    conn = sqlite3.connect(db_path, check_same_thread=False)

    # Instantiate SqliteSaver directly with the connection.
    checkpointer = SqliteSaver(conn=conn)

    # Compile the graph with the persistent checkpointer instance.
    app = workflow.compile(checkpointer=checkpointer)

    # Basic signal handling for clean exit.
    def signal_handler(sig, frame):
        print('\nSignal received, exiting.')
        # The finally block in cli.py should close the connection.
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Return the app and the checkpointer instance (which holds the open connection).
    return app, checkpointer
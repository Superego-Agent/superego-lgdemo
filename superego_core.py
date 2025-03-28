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
from inner_agent_definitions import default_inner_agent_node

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable not set.")

@shout_if_fails
def load_superego_instructions():
    file_path = CONFIG["file_paths"]["superego_instructions"]
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
    result = eval(expression, {"__builtins__": allowed_builtins}, {})
    return f"{result}"

def should_continue_from_superego(state: MessagesState) -> Union[Literal["tools"], Literal["inner_agent"]]:
    """Determine whether to proceed to tools (if superego called one) or directly to the inner agent."""
    last_message = state["messages"][-1]
    # Check if the last message is an AIMessage and has tool_calls
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        # Superego called a tool
        return "tools"
    else:
        # Superego did not call a tool, add debug print and proceed
        print("DEBUG: Superego did not call a tool, proceeding directly to inner_agent.")
        return "inner_agent"

def should_continue_from_tools(state: MessagesState) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state['messages']; last_message = messages[-1]
    if not isinstance(last_message, ToolMessage): return END

    if last_message.name == "superego_decision":
        try:
            # Ensure content is treated as string for comparison
            allow_decision = str(last_message.content).strip().lower() == "true"
            return "inner_agent" if allow_decision else END
        except Exception:
             print(f"[yellow]Warning: Superego decision tool returned non-boolean parseable content: {last_message.content}[/yellow]")
             return END
    else:
        # Any other tool result proceeds to inner_agent
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
        system_prompt += f"\n\n{constitution_content}"
    else:
        system_prompt += "\n\n## Constitution\nNo specific constitution provided for this run."

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt_template | superego_model

    response = chain.invoke({"messages": messages}, config)
    response.name = "superego" 
    return {"messages": [response]}

@shout_if_fails
def create_workflow(superego_model, inner_model) -> Tuple[Annotated[Any, "CompiledGraph"], SqliteSaver]:
    """Creates the graph, checkpointer, and returns the compiled app and checkpointer instance."""
    tools = [superego_decision, calculator]
    tool_node = ToolNode(tools)

    workflow = StateGraph(MessagesState)

    workflow.add_node("superego", lambda state, config: call_superego(state, config, superego_model))
    workflow.add_node("inner_agent", lambda state: default_inner_agent_node(state, inner_model))
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "superego")
    workflow.add_conditional_edges("superego", should_continue_from_superego, {"tools": "tools", "inner_agent": "inner_agent"})
    workflow.add_conditional_edges("tools", should_continue_from_tools, {"inner_agent": "inner_agent", END: END})
    workflow.add_conditional_edges("inner_agent", should_continue_from_inner_agent, {"tools": "tools", END: END})

    db_path = CONFIG.get("sessions_dir", "data/sessions") + "/conversations.db"
    db_dir = os.path.dirname(db_path)
    if db_dir: os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path, check_same_thread=False)

    checkpointer = SqliteSaver(conn=conn)

    app = workflow.compile(checkpointer=checkpointer)

    def signal_handler(sig, frame):
        print('\\nSignal received, exiting.')
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    return app, checkpointer
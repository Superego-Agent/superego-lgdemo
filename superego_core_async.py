import os
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union

import aiosqlite  # Use aiosqlite instead of sqlite3
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

# Import AsyncSqliteSaver instead of SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from config import CONFIG
from inner_agent_definitions import default_inner_agent_node
from keystore import keystore
from utils import shout_if_fails

# The API key will be retrieved from the keystore based on session ID


@shout_if_fails
def load_superego_instructions():
    file_path = CONFIG["file_paths"]["superego_instructions"]
    with open(file_path, encoding="utf-8") as f:
        return f.read()


@tool
def superego_decision(allow: bool, message: str = "") -> str:
    """Make a decision on whether to allow or block the input.

    Args:
        allow: Boolean indicating whether to allow the input
        message: Optional message explaining the decision
    """
    text = (
        "✅ Superego allowed the prompt."
        if allow
        else "❌ Superego blocked the prompt."
    )
    text += f"\n\n{message}" if message else ""
    return text


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result."""
    allowed_builtins = {"abs": abs, "pow": pow, "round": round}
    result = eval(expression, {"__builtins__": allowed_builtins}, {})
    return f"{result}"


def should_continue_from_superego(
    state: MessagesState,
) -> Union[Literal["tools"], Literal["inner_agent"]]:
    """Determine whether to proceed to tools (if superego called one) or directly to the inner agent."""
    last_message = state["messages"][-1]
    # Check if the last message is an AIMessage and has tool_calls
    if isinstance(last_message, AIMessage) and getattr(
        last_message, "tool_calls", None
    ):
        # Superego called a tool
        return "tools"
    else:
        # Superego did not call a tool, add debug print and proceed
        print(
            "DEBUG: Superego did not call a tool, proceeding directly to inner_agent."
        )
        return "inner_agent"


def should_continue_from_tools(
    state: MessagesState,
) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state["messages"]
    last_message = messages[-1]
    if not isinstance(last_message, ToolMessage):
        return END

    if last_message.name == "superego_decision":
        try:
            # Check if the content starts with "Superego allowed the prompt"
            allow_decision = "Superego allowed the prompt" in str(last_message.content)
            return "inner_agent" if allow_decision else END
        except Exception:
            print(
                f"[yellow]Warning: Superego decision tool returned unexpected content: {last_message.content}[/yellow]"
            )
            return END
    else:
        # Any other tool result proceeds to inner_agent
        return "inner_agent"


def should_continue_from_inner_agent(
    state: MessagesState,
) -> Union[Literal["tools"], Literal[END]]:
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and getattr(
        last_message, "tool_calls", None
    ):
        return "tools"
    else:
        return END


@shout_if_fails
def create_models(api_key: Optional[str] = None, session_id: Optional[str] = None):
    """Create the language models for superego and inner agent.

    Args:
        api_key: Optional API key to use directly
        session_id: Optional session ID to retrieve API key from keystore

    Returns:
        Tuple of (superego_model, inner_model) or (None, None) if API key is not set
    """
    # If no API key is provided directly, try to get it from the keystore using session_id
    if not api_key and session_id:
        api_key = keystore.get_key(session_id)
        if api_key:
            print(f"Using API key from keystore for session {session_id}")

    # If still no API key, try environment variable as fallback for backward compatibility
    if not api_key:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            print("Using API key from environment variable (legacy mode)")

    # If no API key is available, return None
    if not api_key:
        print("No API key available from any source")
        return None, None

    try:
        superego_model = ChatAnthropic(
            model=CONFIG["model_name"],
            api_key=api_key,  # Explicitly pass the API key
            streaming=CONFIG.get("streaming", True),
        ).bind_tools([superego_decision])

        inner_model = ChatAnthropic(
            model=CONFIG["model_name"],
            api_key=api_key,  # Explicitly pass the API key
            streaming=CONFIG.get("streaming", True),
        ).bind_tools([calculator])

        return superego_model, inner_model
    except Exception as e:
        print(f"Error creating models: {e}")
        return None, None


def call_superego(
    state: MessagesState, config: dict, superego_model
) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    configurable = config.get("configurable", {})
    constitution_content = configurable.get("constitution_content", "")
    adherence_levels_text = configurable.get(
        "adherence_levels_text", ""
    )  # Get adherence levels text
    superego_instructions = load_superego_instructions()

    system_prompt = f"{superego_instructions}"
    if constitution_content:
        system_prompt += f"\n\n{constitution_content}"
    else:
        system_prompt += (
            "\n\n## Constitution\nNo specific constitution provided for this run."
        )

    # Append adherence levels if provided
    if adherence_levels_text:
        system_prompt += f"\n\n{adherence_levels_text}"

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_prompt), MessagesPlaceholder(variable_name="messages")]
    )
    chain = prompt_template | superego_model

    response = chain.invoke({"messages": messages}, config)
    response.name = "superego"
    return {"messages": [response]}


def run_inner_agent_only(
    state: MessagesState, inner_model
) -> Dict[str, List[BaseMessage]]:
    """Run only the inner agent without superego oversight."""
    return default_inner_agent_node(state, inner_model)


@shout_if_fails
async def create_workflow(
    superego_model, inner_model, session_id: Optional[str] = None
) -> Tuple[
    Annotated[Any, "CompiledGraph"], AsyncSqliteSaver, Annotated[Any, "CompiledGraph"]
]:
    """Creates the graph, checkpointer, and returns the compiled app, checkpointer instance, and inner-agent-only app."""
    # Setup database connection for checkpointing - using aiosqlite
    db_path = CONFIG.get("sessions_dir", "data/sessions") + "/conversations.db"
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # Use aiosqlite instead of sqlite3
    conn = await aiosqlite.connect(db_path)
    # Use AsyncSqliteSaver instead of SqliteSaver
    checkpointer = AsyncSqliteSaver(conn=conn)

    # If models are not available, return None for the apps but still return the checkpointer
    if superego_model is None or inner_model is None:
        print(
            "Warning: Models not available. Returning None for apps but still setting up checkpointer."
        )
        return None, checkpointer, None

    tools = [superego_decision, calculator]
    tool_node = ToolNode(tools)

    # Main workflow with superego
    workflow = StateGraph(MessagesState)

    workflow.add_node(
        "superego", lambda state, config: call_superego(state, config, superego_model)
    )
    workflow.add_node(
        "inner_agent", lambda state: default_inner_agent_node(state, inner_model)
    )
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "superego")
    workflow.add_conditional_edges(
        "superego",
        should_continue_from_superego,
        {"tools": "tools", "inner_agent": "inner_agent"},
    )
    workflow.add_conditional_edges(
        "tools", should_continue_from_tools, {"inner_agent": "inner_agent", END: END}
    )
    workflow.add_conditional_edges(
        "inner_agent", should_continue_from_inner_agent, {"tools": "tools", END: END}
    )

    # Inner agent only workflow (subgraph 2)
    inner_workflow = StateGraph(MessagesState)
    inner_workflow.add_node(
        "inner_agent", lambda state: default_inner_agent_node(state, inner_model)
    )
    inner_workflow.add_node("tools", tool_node)

    inner_workflow.add_edge(START, "inner_agent")
    inner_workflow.add_conditional_edges(
        "inner_agent", should_continue_from_inner_agent, {"tools": "tools", END: END}
    )
    inner_workflow.add_conditional_edges(
        "tools", lambda state: "inner_agent", {"inner_agent": "inner_agent"}
    )

    # Compile both workflows
    app = workflow.compile(checkpointer=checkpointer)
    inner_app = inner_workflow.compile(checkpointer=checkpointer)

    # Removed custom signal handler (lines 170-175) as it conflicts with
    # Uvicorn's signal management, especially with reload enabled.
    # Uvicorn will handle SIGINT/SIGTERM for graceful shutdown.

    return app, checkpointer, inner_app

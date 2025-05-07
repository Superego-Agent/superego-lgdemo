import os
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Union

import aiosqlite  # Use aiosqlite instead of sqlite3
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
# TODO: Verify correct VertexAI import if needed, assuming ChatVertexAI for now
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from pydantic import ValidationError

# Import AsyncSqliteSaver instead of SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from backend_models import ModelConfig
from config import CONFIG
from inner_agent_definitions import default_inner_agent_node
from keystore import keystore # Import the keystore instance
from utils import shout_if_fails
# Removed top-level import to break circular dependency:
# from backend_server_async import ENV_API_KEYS

# API keys are now fetched dynamically within node functions


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


# create_models function removed as model instantiation is now dynamic within nodes

def call_superego(
    state: MessagesState, config: dict
) -> Dict[str, List[BaseMessage]]:
    """Dynamically instantiates and calls the Superego LLM based on config."""
    messages = state["messages"]
    configurable = config.get("configurable", {})
    session_id = configurable.get("session_id") # Get session_id from config

    # --- 1. Access and Validate Model Configuration ---
    model_config_dict = configurable.get("model_config")
    if not model_config_dict:
        raise ValueError(
            "Missing 'model_config' in run configuration (configurable)."
        )

    try:
        model_config = ModelConfig.model_validate(model_config_dict)
    except ValidationError as e:
        # Re-raise clearly indicating the source of the error
        raise ValueError(f"Invalid 'model_config' provided: {e}") from e

    # --- 2. Fetch API Key with Fallback ---
    # Import ENV_API_KEYS here, inside the function, to avoid circular import
    from backend_server_async import ENV_API_KEYS
    provider = model_config.provider
    user_api_key = keystore.get_key(session_id, provider) if session_id else None
    env_api_key = ENV_API_KEYS.get(provider, "")

    api_key_to_use = None
    key_source = "none"

    # Prioritize non-empty user key
    if user_api_key: # Check if not None and not empty string
        api_key_to_use = user_api_key
        key_source = "user"
        print(f"Using user-provided API key for provider '{provider}' in session '{session_id}'.")
    # Fallback to non-empty .env key if user key is missing or empty
    elif env_api_key:
        api_key_to_use = env_api_key
        key_source = "env"
        print(f"User key for provider '{provider}' missing or empty in session '{session_id}'. Falling back to .env key.")
    else:
        # Both user key and .env key are missing/empty
        print(f"No API key found for provider '{provider}' in session '{session_id}' or .env file.")

    # --- 3. Validate Key Presence (if required by provider) ---
    # Vertex AI uses Application Default Credentials (ADC) by default, so API key might not be needed/provided
    if not api_key_to_use and provider != "google_vertex":
        error_msg = f"Missing required API key for provider '{provider}'. "
        if session_id:
            error_msg += f"No key found in session '{session_id}' (user-provided) or in the .env file (fallback)."
        else:
            error_msg += f"No session_id provided, and no key found in the .env file (fallback)."
        raise ValueError(error_msg)

    # --- 4. Dynamic LLM Client Instantiation ---
    # Use api_key_to_use which holds either the user key or the fallback .env key
    llm = None
    try:
        if model_config.provider == "anthropic":
            params = model_config.anthropic_params.model_dump(exclude_none=True) if model_config.anthropic_params else {}
            llm = ChatAnthropic(
                model=model_config.name,
                api_key=api_key_to_use, # Use the determined key
                streaming=CONFIG.get("streaming", True),
                **params,
            )
        elif model_config.provider == "openai":
            params = model_config.openai_params.model_dump(exclude_none=True) if model_config.openai_params else {}
            llm = ChatOpenAI(
                model=model_config.name,
                api_key=api_key_to_use, # Use the determined key
                streaming=CONFIG.get("streaming", True),
                **params,
            )
        elif model_config.provider == "google_genai":
            params = model_config.google_genai_params.model_dump(exclude_none=True) if model_config.google_genai_params else {}
            llm = ChatGoogleGenerativeAI(
                model=model_config.name,
                google_api_key=api_key_to_use, # Use the determined key
                # streaming=CONFIG.get("streaming", True), # TODO: Check if streaming is supported/needed here
                **params,
            )
        elif model_config.provider == "google_vertex":
            params = model_config.google_vertex_params.model_dump(exclude_none=True) if model_config.google_vertex_params else {}
            # Example check: LangChain's ChatVertexAI might require 'project'
            # if 'project' not in params and not os.getenv('GOOGLE_CLOUD_PROJECT'):
            #     raise ValueError("Missing 'project' parameter for google_vertex provider in model_config or GOOGLE_CLOUD_PROJECT env var.")
            llm = ChatVertexAI(
                model_name=model_config.name, # Note: param name is model_name for Vertex
                # api_key is not typically used directly with Vertex ADC
                # streaming=CONFIG.get("streaming", True), # TODO: Check streaming support
                **params,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {model_config.provider}")

    except Exception as e:
        # Catch potential instantiation errors (e.g., invalid model name for provider)
       # Add context about which key source failed if possible
       if key_source == "user":
           error_detail = f"The API key you provided for provider '{provider}' in session '{session_id}' may be invalid or lack permissions for model '{model_config.name}'."
       elif key_source == "env":
           error_detail = f"The fallback API key from the .env file for provider '{provider}' may be invalid or lack permissions for model '{model_config.name}'."
       else: # Should not happen if ValueError check passed, but include for completeness
            error_detail = f"An unexpected error occurred trying to instantiate the LLM client for provider '{provider}' with model '{model_config.name}' (key status unknown)."

       # Include the original error from the library for technical detail
       raise RuntimeError(f"{error_detail} Original error: {e}") from e

   # Bind the appropriate tool for Superego
    superego_llm = llm.bind_tools([superego_decision])

    # --- 5. Prepare Prompt and Invoke ---
    constitution_content = configurable.get("constitution_content", "")
    adherence_levels_text = configurable.get("adherence_levels_text", "")
    superego_instructions = load_superego_instructions()

    system_prompt = f"{superego_instructions}"
    if constitution_content:
        system_prompt += f"\n\n{constitution_content}"
    else:
        system_prompt += (
            "\n\n## Constitution\nNo specific constitution provided for this run."
        )
    if adherence_levels_text:
        system_prompt += f"\n\n{adherence_levels_text}"

    prompt_template = ChatPromptTemplate.from_messages(
        [("system", system_prompt), MessagesPlaceholder(variable_name="messages")]
    )
    chain = prompt_template | superego_llm

    response = chain.invoke({"messages": messages}, config)
    response.name = "superego" # Tag the response source
    return {"messages": [response]}


# Note: run_inner_agent_only is removed as the logic should be within default_inner_agent_node
# def run_inner_agent_only(...) -> ...: ...


@shout_if_fails
async def create_workflow(
    session_id: Optional[str] = None # Removed model args
) -> Tuple[
    Optional[Annotated[Any, "CompiledGraph"]], # Can be None if setup fails
    AsyncSqliteSaver,
    Optional[Annotated[Any, "CompiledGraph"]] # Can be None if setup fails
]:
    """Creates the graph, checkpointer, and returns the compiled app, checkpointer instance, and inner-agent-only app.
       Models are now instantiated dynamically within the graph nodes."""
    # Setup database connection for checkpointing - using aiosqlite
    db_path = CONFIG.get("sessions_dir", "data/sessions") + "/conversations.db"
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = None # Initialize conn to None
    try:
        # Use aiosqlite instead of sqlite3
        conn = await aiosqlite.connect(db_path)
        # Use AsyncSqliteSaver instead of SqliteSaver
        checkpointer = AsyncSqliteSaver(conn=conn)

        # Model availability check removed - instantiation happens in nodes

        # Define tools available to both workflows
        # Note: The inner agent node will need its own logic to bind only the tools it should use (e.g., calculator)
        tools = [superego_decision, calculator]
        tool_node = ToolNode(tools) # This node executes any tool called by the preceding LLM

        # --- Main workflow with superego ---
        workflow = StateGraph(MessagesState)

        # Nodes now fetch config and instantiate models internally
        workflow.add_node("superego", call_superego) # Pass only state and config
        # The inner_agent node needs similar dynamic instantiation logic within inner_agent_definitions.py
        # For now, assume default_inner_agent_node is updated or will be updated separately to handle config
        workflow.add_node("inner_agent", default_inner_agent_node) # Pass only state (it gets config implicitly)
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

        # --- Inner agent only workflow (subgraph 2) ---
        inner_workflow = StateGraph(MessagesState)
        # Assume default_inner_agent_node handles its own model instantiation based on config
        inner_workflow.add_node("inner_agent", default_inner_agent_node)
        # Inner agent might only use specific tools (e.g., calculator)
        # The ToolNode executes whatever the LLM called. Binding happens in the LLM node.
        inner_workflow.add_node("tools", tool_node) # Re-use the same tool execution node

        inner_workflow.add_edge(START, "inner_agent")
        inner_workflow.add_conditional_edges(
            "inner_agent", should_continue_from_inner_agent, {"tools": "tools", END: END}
        )
        # After tools in inner_workflow, decide where to go next.
        # If the tool was calculator, maybe loop back to inner_agent? Or end?
        # For simplicity, let's assume it might call another tool or end.
        # Reusing should_continue_from_inner_agent might be wrong here if tools always lead back to agent.
        # Let's assume for now tools lead back to the agent if more work is needed, or end.
        # This conditional edge might need refinement based on desired inner_agent loop behavior.
        # A simple loop back for now:
        inner_workflow.add_conditional_edges(
           "tools", lambda state: "inner_agent", {"inner_agent": "inner_agent"} # Simplified loop back
        )


        # Compile both workflows
        app = workflow.compile(checkpointer=checkpointer)
        inner_app = inner_workflow.compile(checkpointer=checkpointer)

        # Removed custom signal handler

        return app, checkpointer, inner_app

    except Exception as e:
        print(f"Error during workflow creation or compilation: {e}")
        # Ensure connection is closed if it was opened and an error occurred
        if conn:
            await conn.close()
        # Return None for apps if setup fails, but still return checkpointer if created
        # If checkpointer creation failed, conn would be None, checkpointer wouldn't exist yet
        # If conn succeeded but checkpointer failed, checkpointer might be partially initialized
        # For simplicity, return None for apps, and checkpointer if it exists, otherwise None
        checkpointer_to_return = checkpointer if 'checkpointer' in locals() else None
        # If conn failed, checkpointer is None. If checkpointer failed, it's None.
        # If compilation failed after checkpointer success, return the checkpointer.
        return None, checkpointer_to_return, None

# superego-lgdemo/superego_core.py (Refactored & Corrected)
import os
import json
import uuid
import time
from pathlib import Path
from typing import Dict, List, Any, Union, Literal, Optional
from dataclasses import dataclass, asdict, field

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from config import CONFIG
from constitution_manager import constitution_manager

# --- Data Models ---
@dataclass
class SessionState:
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        expected_fields = cls.__annotations__.keys()
        filtered_data = {k: v for k, v in data.items() if k in expected_fields}
        return cls(**filtered_data)

# --- Session Management (Simplified for CLI handling state) ---
class SessionManager:
    def __init__(self, sessions_dir: str = CONFIG["sessions_dir"]):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: Dict[str, SessionState] = {}

    def _get_session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        session = SessionState(session_id=session_id)
        self.active_sessions[session_id] = session
        self._save_session(session_id)
        return session_id

    def _save_session(self, session_id: str) -> None:
        if session_id not in self.active_sessions:
            return
        session = self.active_sessions[session_id]
        session.updated_at = time.time()
        try:
            with open(self._get_session_path(session_id), 'w') as f:
                json.dump(session.to_dict(), f, indent=2, default=str)
        except Exception as e:
             print(f"Warning: Failed to save session {session_id}: {e}")


    def load_session(self, session_id: str) -> Optional[SessionState]:
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        session_path = self._get_session_path(session_id)
        if not session_path.exists():
            return None
        try:
            with open(session_path, 'r') as f:
                data = json.load(f)
                session = SessionState.from_dict(data)
                self.active_sessions[session_id] = session
                return session
        except Exception as e:
            print(f"Warning: Could not load session {session_id}: {e}")
            return None

    def get_all_sessions(self) -> List[str]:
        self.active_sessions = {} # Force reload from disk
        session_ids = []
        for path in self.sessions_dir.glob("*.json"):
            session_id = path.stem
            if self.load_session(session_id):
                 session_ids.append(session_id)
        return session_ids

    def get_message_history_from_saved_state(self, session_id: str) -> List[Dict[str, Any]]:
        """Gets message history from the last saved JSON state (potentially stale)."""
        session = self.load_session(session_id)
        return session.messages if session else []

# --- Environment Check ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")

# --- Instruction Loading ---
def load_superego_instructions():
    try:
        with open(CONFIG["file_paths"]["superego_instructions"]) as f:
            return f.read()
    except FileNotFoundError as e:
        raise ValueError(f"Could not load superego instructions: {e.filename}") from e

def load_inner_agent_instructions():
    try:
        with open(CONFIG["file_paths"]["inner_agent_instructions"]) as f:
            return f.read()
    except FileNotFoundError as e:
        raise ValueError(f"Could not load inner agent instructions: {e.filename}") from e

def load_active_constitution():
    constitution_id = CONFIG["active_constitution"]
    content = constitution_manager.get_constitution_content(constitution_id)
    if not content:
        raise ValueError(f"Could not load constitution: {constitution_id}")
    return content

def reload_instructions():
    pass

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

tools = [superego_decision, calculator]
tool_node = ToolNode(tools) # Node to execute tools

# --- Routing Logic ---
def should_continue_from_tools(state: MessagesState) -> Union[Literal["inner_agent"], Literal[END]]:
    messages = state['messages']
    last_message = messages[-1]

    if isinstance(last_message, ToolMessage):
        if last_message.name == "superego_decision":
            return "inner_agent" if last_message.content == "true" else END
        else:
            # Assume other tools were called by inner_agent, return to it
            return "inner_agent"
    # Should ideally not happen if graph structure is correct
    return END


def should_continue_from_inner_agent(state: MessagesState) -> Union[Literal["tools"], Literal[END]]:
    last_message = state["messages"][-1]
    return "tools" if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls else END

# --- Prompt Creation ---
def create_superego_prompt():
    superego_instructions = load_superego_instructions()
    constitution = load_active_constitution()
    return ChatPromptTemplate.from_messages([
        ("system", f"{superego_instructions}\n\n{constitution}"),
        MessagesPlaceholder(variable_name="messages")
    ])

def create_inner_prompt():
    inner_agent_instructions = load_inner_agent_instructions()
    return ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])

# --- Model Creation ---
def create_models():
    """Creates and returns models bound with their respective tools."""
    superego_model_raw = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG["streaming"]
    )
    superego_model = superego_model_raw.bind_tools([superego_decision])

    inner_model_raw = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG["streaming"]
    )
    inner_model = inner_model_raw.bind_tools(tools) # Inner agent gets all tools

    return superego_model, inner_model

# --- Graph Node Functions ---
def call_superego(state: MessagesState, config: dict, superego_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]

    constitution = config.get("configurable", {}).get("constitution", "") # Safely get constitution
    if not constitution:
         print("Warning: No constitution found in config for superego node.")

    superego_instructions = load_superego_instructions()
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"{superego_instructions}\n\n{constitution}"), # Combine instructions and constitution
        MessagesPlaceholder(variable_name="messages")
    ])

    formatted_prompt = prompt.invoke({"messages": messages})
    response = superego_model.invoke(formatted_prompt)
    return {"messages": [response]}

def inner_agent(state: MessagesState, inner_model) -> Dict[str, List[BaseMessage]]:
    messages = state["messages"]
    prompt = create_inner_prompt()
    formatted_prompt = prompt.invoke({"messages": messages})
    response = inner_model.invoke(formatted_prompt)
    return {"messages": [response]}

# --- Global Session Manager Instance ---
session_manager = SessionManager()

# --- Workflow Creation ---
def create_workflow(superego_model, inner_model):
    workflow = StateGraph(MessagesState)

    workflow.add_node("superego", lambda state, config: call_superego(state, config, superego_model))

    workflow.add_node("tools", tool_node)
    workflow.add_node("inner_agent", lambda state: inner_agent(state, inner_model)) # No change needed if inner_agent doesn't need config yet

    workflow.add_edge(START, "superego")
    workflow.add_edge("superego", "tools") # Superego always calls its tool

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

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)

# --- Client API Functions ---
def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Gets an existing session ID or creates a new one."""
    if session_id and session_manager.load_session(session_id):
        return session_id
    return session_manager.create_session()

def get_all_sessions() -> List[str]:
    """Gets a list of all session IDs known to the SessionManager."""
    return session_manager.get_all_sessions()

def get_message_history(session_id: str) -> List[BaseMessage]:
    """Gets message history using the checkpointer associated with the compiled graph."""
    if 'graph' not in globals():
        print("Warning: Graph object not found globally for get_message_history.")

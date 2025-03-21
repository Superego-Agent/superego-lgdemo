import os
import json
import uuid
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Union, Literal, Optional, Generator
from dataclasses import dataclass, asdict, field

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

# Configuration
CONFIG = {
    "model_name": "claude-3-7-sonnet-latest",
    "file_paths": {
        "superego_instructions": "data/agent_instructions/input_superego.md",
        "inner_agent_instructions": "data/agent_instructions/inner_agent_default.md",
    },
    "active_constitution": "default",
    "streaming": True,
    "sessions_dir": "data/sessions",
    "constitutions_dir": "data/constitutions"
}

Path(CONFIG["sessions_dir"]).mkdir(parents=True, exist_ok=True)

# Data models
@dataclass
class StreamEvent:
    node_name: str
    content: str 
    timestamp: float = field(default_factory=time.time)
    
@dataclass
class SessionState:
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    current_node: Optional[str] = None
    superego_decision: Optional[bool] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        return cls(**data)

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
        
        with open(self._get_session_path(session_id), 'w') as f:
            json.dump(session.to_dict(), f, indent=2, default=str)
    
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
        except (json.JSONDecodeError, KeyError):
            return None
    
    def get_all_sessions(self) -> List[str]:
        for path in self.sessions_dir.glob("*.json"):
            session_id = path.stem
            if session_id not in self.active_sessions:
                self.load_session(session_id)
                
        return list(self.active_sessions.keys())
    
    def add_message(self, session_id: str, message: Union[HumanMessage, Dict[str, Any]]) -> bool:
        session = self.load_session(session_id)
        if not session:
            return False
            
        if isinstance(message, BaseMessage):
            msg_dict = {"type": message.__class__.__name__, "content": message.content}
        else:
            msg_dict = message
            
        session.messages.append(msg_dict)
        self._save_session(session_id)
        return True
    
    def add_event(self, session_id: str, event: Union[StreamEvent, Dict[str, Any]]) -> bool:
        session = self.load_session(session_id)
        if not session:
            return False
            
        event_dict = asdict(event) if isinstance(event, StreamEvent) else event
        session.events.append(event_dict)
        
        if "node_name" in event_dict:
            session.current_node = event_dict["node_name"]
            
        if event_dict.get("node_name") == "tools" and "tool_name" in event_dict:
            if event_dict.get("tool_name") == "superego_decision":
                session.superego_decision = event_dict.get("tool_result") == "true"
            
        self._save_session(session_id)
        return True
    
    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.load_session(session_id)
        if not session:
            return None
            
        return session.to_dict()

# Check for API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")

# Read instructions when needed
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
    constitution_path = Path(CONFIG["constitutions_dir"]) / f"{constitution_id}.md"
    try:
        with open(constitution_path) as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(f"Could not load constitution: {constitution_id}")

# Define tools
@tool
def superego_decision(allow: bool) -> bool:
    """Make a decision on whether to allow or block the input"""
    return allow

@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.
    Examples of expressions: 2+2, 5*6, (7+3)/2, 8**2"""
    try:
        # Safely evaluate the expression
        result = eval(expression, {"__builtins__": {}}, 
                      {"abs": abs, "pow": pow, "round": round})
        return f"{result}"
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"

# All tools available for both agents
tools = [superego_decision, calculator]
tool_node = ToolNode(tools)

def should_continue_from_tools(state) -> Union[Literal["inner_agent"], Literal["end"]]:
    """Route based on superego decision"""
    from langchain_core.messages import ToolMessage
    messages = state["messages"]
    tool_messages = [msg for msg in messages if isinstance(msg, ToolMessage)]
    
    if not tool_messages:
        return END
    
    # Get the last tool message and check its name
    last_tool = tool_messages[-1]
    
    # If it's a superego_decision tool with "true", continue to inner_agent
    if last_tool.content == "true":
        return "inner_agent"
    
    # If it's any other tool (like calculator), we need to ensure the workflow
    # continues properly to show the tool result
    if hasattr(last_tool, "name") and last_tool.name != "superego_decision":
        # For non-superego_decision tools, we should still continue to inner_agent
        # This ensures the tool result is properly displayed
        return "inner_agent"
    
    # Otherwise end the workflow
    return END

def should_continue_from_inner_agent(state) -> Union[Literal["tools"], Literal["end"]]:
    """Route based on whether inner agent is using a tool"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the last message has tool calls, route to tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    # Otherwise end the workflow
    return END

# Define prompt creation functions
def create_superego_prompt():
    superego_instructions = load_superego_instructions()
    constitution = load_active_constitution()
    return ChatPromptTemplate.from_messages([
        ("system", superego_instructions + "\n\n" + constitution),
        MessagesPlaceholder(variable_name="messages")
    ])

def create_inner_prompt():
    inner_agent_instructions = load_inner_agent_instructions()
    return ChatPromptTemplate.from_messages([
        ("system", inner_agent_instructions),
        MessagesPlaceholder(variable_name="messages")
    ])

def create_models():
    """Create and return the models for superego and inner agent"""
    superego_model = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG["streaming"]
    ).bind_tools(tools)  # Use all tools for the superego agent
    
    inner_model = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG["streaming"]
    )

    return superego_model, inner_model

def call_superego(state, superego_model) -> Dict:
    """Have the superego agent evaluate a message against the constitution"""
    messages = state["messages"]
    prompt = create_superego_prompt()
    response = superego_model.invoke(prompt.format(messages=messages))
    return {"messages": messages + [response]}

def inner_agent(state, inner_model) -> Dict:
    """Run the inner agent to respond to allowed messages"""
    messages = state["messages"]
    prompt = create_inner_prompt()
    # Enable inner agent to use all tools including calculator
    inner_with_tools = inner_model.bind_tools(tools)
    response = inner_with_tools.invoke(prompt.format(messages=messages))
    return {"messages": messages + [response]}

# Global session manager
session_manager = SessionManager()

# Constitution Management
def get_available_constitutions() -> List[Dict[str, Any]]:
    """List all available constitutions with metadata"""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    result = []
    
    for constitution_path in constitutions_dir.glob("*.md"):
        constitution_id = constitution_path.stem
        
        try:
            with open(constitution_path, 'r') as f:
                first_line = f.readline().strip()
                title = first_line.replace('#', '').strip()
                
                stats = constitution_path.stat()
                
                result.append({
                    "id": constitution_id,
                    "title": title,
                    "path": str(constitution_path),
                    "size": stats.st_size,
                    "last_modified": stats.st_mtime
                })
        except Exception as e:
            result.append({
                "id": constitution_id,
                "path": str(constitution_path),
                "error": str(e)
            })
    
    return sorted(result, key=lambda x: x["title"])

def get_constitution_content(constitution_id: str) -> Optional[str]:
    """Get the content of a specific constitution"""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    constitution_path = constitutions_dir / f"{constitution_id}.md"
    
    if not constitution_path.exists():
        return None
        
    try:
        with open(constitution_path, 'r') as f:
            return f.read()
    except Exception:
        return None

def save_constitution(constitution_id: str, content: str) -> bool:
    """Save a constitution (create new or update existing)"""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    constitution_path = constitutions_dir / f"{constitution_id}.md"
    
    try:
        with open(constitution_path, 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False

def delete_constitution(constitution_id: str) -> bool:
    """Delete a constitution"""
    if constitution_id == "default":
        return False
        
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    constitution_path = constitutions_dir / f"{constitution_id}.md"
    
    if not constitution_path.exists():
        return False
        
    try:
        constitution_path.unlink()
        return True
    except Exception:
        return False

def set_active_constitution(constitution_id: str) -> bool:
    """Set the active constitution for the application"""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    constitution_path = constitutions_dir / f"{constitution_id}.md"
    
    if not constitution_path.exists():
        return False
        
    CONFIG["active_constitution"] = constitution_id
    return True

def get_active_constitution() -> str:
    """Get the currently active constitution ID"""
    return CONFIG["active_constitution"]

def create_workflow(superego_model, inner_model):
    """Create and return the workflow graph"""
    workflow = StateGraph(MessagesState)
    # Define node functions with bound models
    def call_superego_with_model(state):
        return call_superego(state, superego_model)
    
    def inner_agent_with_model(state):
        return inner_agent(state, inner_model)
    
    # Add nodes
    workflow.add_node("superego", call_superego_with_model)
    workflow.add_node("tools", tool_node)  # Use ToolNode directly
    workflow.add_node("inner_agent", inner_agent_with_model)
    
    # Add edges
    workflow.add_edge(START, "superego")
    workflow.add_edge("superego", "tools")
    
    # Conditional edge from tools to inner_agent or END
    workflow.add_conditional_edges(
        "tools",
        should_continue_from_tools,
        {
            "inner_agent": "inner_agent",
            END: END
        }
    )
    
    # Conditional edge from inner_agent to tools or END
    workflow.add_conditional_edges(
        "inner_agent",
        should_continue_from_inner_agent,
        {
            "tools": "tools",
            END: END
        }
    )
    
    workflow.set_entry_point("superego")
    
    # Memory-based persistence
    memory_saver = MemorySaver()
    
    return workflow.compile(checkpointer=memory_saver)

# Client API
def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get an existing session or create a new one"""
    if session_id and session_manager.load_session(session_id):
        return session_id
    return session_manager.create_session()

def get_all_sessions() -> List[str]:
    """Get a list of all session IDs"""
    return session_manager.get_all_sessions()

def add_user_message(session_id: str, message: str) -> bool:
    """Add a user message to a session"""
    return session_manager.add_message(session_id, HumanMessage(content=message))

def get_message_history(session_id: str) -> List[Dict[str, Any]]:
    """Get the message history for a session"""
    session = session_manager.load_session(session_id)
    if not session:
        return []
    return session.messages

def run_session(session_id: str, app) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
    """Run a session and yield streaming updates"""
    session = session_manager.load_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Get last human message
    last_message = None
    for msg in reversed(session.messages):
        if msg.get("type") == "HumanMessage":
            last_message = HumanMessage(content=msg.get("content", ""))
            break
    
    if not last_message:
        raise ValueError("No human message found in session")
    
    state = {"messages": [last_message]}
    config = {"configurable": {"thread_id": session_id}}
    
    for stream_type, chunk in app.stream(state, config, stream_mode=["messages", "values"]):
        event = {
            "stream_type": stream_type,
            "timestamp": time.time()
        }
        
        if stream_type == "messages":
            message_chunk, metadata = chunk
            node_name = metadata.get("langgraph_node", "")
            
            # Extract text content only, tool calls are handled in values stream
            content = ""
            if hasattr(message_chunk, "content"):
                if isinstance(message_chunk.content, str):
                    content = message_chunk.content
                elif isinstance(message_chunk.content, list):
                    for item in message_chunk.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            content += item.get("text", "")
            
            event.update({
                "node_name": node_name,
                "content": content
            })
            
        elif stream_type == "values":
            node_name = chunk.get("langgraph_node")
            if node_name:
                event["node_name"] = node_name
            
            # Only extract tool calls from the last message if it's an AIMessage
            if "messages" in chunk and len(chunk["messages"]) > 0:
                last_message = chunk["messages"][-1]
                
                # Check if it's an AIMessage with tool_calls
                if (isinstance(last_message, AIMessage) and 
                    hasattr(last_message, "tool_calls") and 
                    last_message.tool_calls):
                    
                    tool_call = last_message.tool_calls[0]
                    calling_agent = "inner_agent" if node_name == "inner_agent" else "superego"
                    
                    event.update({
                        "tool_name": tool_call["name"],
                        "tool_input": tool_call.get("args", {}),
                        "tool_id": tool_call.get("id", ""),
                        "agent": calling_agent,
                        "stage": "call",
                        "timestamp": time.time()
                    })
                
                # Extract tool results when available
                if "tool_result" in chunk:
                    # Determine which agent called this tool based on the tool name
                    # superego only uses superego_decision, inner_agent uses other tools
                    tool_name = event.get("tool_name", "")
                    calling_agent = "superego" if tool_name == "SUPEREGO_DECISION" else "inner_agent"
                    event.update({
                        "tool_result": chunk["tool_result"],
                        "agent": calling_agent,
                        "stage": "result"
                    })
        
        session_manager.add_event(session_id, event)
        yield event
    
    return session_manager.get_session_state(session_id)

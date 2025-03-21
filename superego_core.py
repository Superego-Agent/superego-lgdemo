import os
import json
import uuid
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any, Union, Literal, Optional, Generator
from operator import itemgetter
from dataclasses import dataclass, asdict, field

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START, MessagesState
from langgraph.prebuilt import ToolNode

# Configuration constants
CONFIG = {
    "model_name": "claude-3-7-sonnet-latest",
    "file_paths": {
        "superego_instructions": "data/agent_instructions/input_superego.md",
        "constitution": "data/constitutions/default.md",
        "inner_agent_instructions": "data/agent_instructions/inner_agent_default.md",
    },
    "streaming": True,
    "sessions_dir": "data/sessions",  # Directory for session persistence
    "constitutions_dir": "data/constitutions"  # Directory for constitutions
}

# Ensure sessions directory exists
Path(CONFIG["sessions_dir"]).mkdir(parents=True, exist_ok=True)

# Data models for session state
@dataclass
class StreamEvent:
    """Represent a streaming event from an agent."""
    node_name: str
    content: str 
    timestamp: float = field(default_factory=time.time)
    
@dataclass
class SessionState:
    """Store the complete state of a conversation session."""
    session_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    current_node: Optional[str] = None
    superego_decision: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the session state to a dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionState':
        """Create a SessionState instance from a dictionary."""
        return cls(**data)

class SessionManager:
    """Manage conversation sessions with persistence."""
    
    def __init__(self, sessions_dir: str = CONFIG["sessions_dir"]):
        """Initialize the session manager."""
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: Dict[str, SessionState] = {}
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get the path to the session file."""
        return self.sessions_dir / f"{session_id}.json"
    
    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        session = SessionState(session_id=session_id)
        self.active_sessions[session_id] = session
        self._save_session(session_id)
        return session_id
    
    def _save_session(self, session_id: str) -> None:
        """Save the session state to a file."""
        if session_id not in self.active_sessions:
            return
            
        session = self.active_sessions[session_id]
        session.updated_at = time.time()
        
        with open(self._get_session_path(session_id), 'w') as f:
            json.dump(session.to_dict(), f, indent=2, default=str)
    
    def load_session(self, session_id: str) -> Optional[SessionState]:
        """Load a session from its ID, either from memory or disk."""
        # Return from memory if available
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Try to load from disk
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
        """Get a list of all session IDs."""
        # Load any sessions from disk that aren't in memory
        for path in self.sessions_dir.glob("*.json"):
            session_id = path.stem
            if session_id not in self.active_sessions:
                self.load_session(session_id)
                
        return list(self.active_sessions.keys())
    
    def add_message(self, session_id: str, message: Union[HumanMessage, Dict[str, Any]]) -> bool:
        """Add a message to the session."""
        session = self.load_session(session_id)
        if not session:
            return False
            
        # Convert message to dict for storage if needed
        if isinstance(message, BaseMessage):
            # Simple serialization for message objects
            msg_dict = {"type": message.__class__.__name__, "content": message.content}
        else:
            msg_dict = message
            
        session.messages.append(msg_dict)
        self._save_session(session_id)
        return True
    
    def add_event(self, session_id: str, event: Union[StreamEvent, Dict[str, Any]]) -> bool:
        """Add a streaming event to the session."""
        session = self.load_session(session_id)
        if not session:
            return False
            
        # Convert event to dict for storage if needed
        if isinstance(event, StreamEvent):
            event_dict = asdict(event)
        else:
            event_dict = event
            
        session.events.append(event_dict)
        
        # Update current node if this is a node transition
        if "node_name" in event_dict:
            session.current_node = event_dict["node_name"]
            
        # Update superego decision if this is from the tools node
        if event_dict.get("node_name") == "tools" and "tool_name" in event_dict:
            session.superego_decision = {
                "decision": event_dict["tool_name"],
                "reason": event_dict.get("tool_input", ""),
                "timestamp": event_dict.get("timestamp", time.time())
            }
            
        self._save_session(session_id)
        return True
    
    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the current state of a session."""
        session = self.load_session(session_id)
        if not session:
            return None
            
        return session.to_dict()

# Load environment variables
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")

# Load agent instructions and constitution
def load_instructions():
    """Load all instruction files"""
    try:
        with open(CONFIG["file_paths"]["superego_instructions"]) as f:
            superego_instructions = f.read()
        
        with open(CONFIG["file_paths"]["constitution"]) as f:
            constitution = f.read()
        
        with open(CONFIG["file_paths"]["inner_agent_instructions"]) as f:
            inner_agent_instructions = f.read()
            
        return superego_instructions, constitution, inner_agent_instructions
    except FileNotFoundError as e:
        raise ValueError(f"Could not load instruction file: {e.filename}") from e

# Load instruction content
SUPEREGO_INSTRUCTIONS, CONSTITUTION, INNER_AGENT_INSTRUCTIONS = load_instructions()

# Define tools for superego agent
@tool
def ALLOW(reason: str) -> str:
    """Allow the user input to proceed to the inner agent"""
    return f"ALLOWED: {reason}"

@tool
def BLOCK(reason: str) -> str:
    """Block the user input from proceeding"""
    return f"BLOCKED: {reason}"

# Define superego tools
superego_tools = [ALLOW, BLOCK]

def parse_tool_call(message: AIMessage) -> Dict[str, Any]:
    """Extract tool call information from various message formats."""
    tool_info = {
        "tool_called": False,
        "tool_name": None,
        "tool_input": None,
        "tool_arguments": None
    }
    
    if not isinstance(message, AIMessage) or not hasattr(message, "content"):
        return tool_info
    
    # Check for Claude's content format (list of dict items)
    if isinstance(message.content, list):
        for item in message.content:
            # Standard Claude tool_use format
            if isinstance(item, dict) and item.get("type") == "tool_use":
                tool_info["tool_called"] = True
                tool_info["tool_name"] = item.get("name")
                
                # Extract arguments
                arguments = item.get("input", {})
                if isinstance(arguments, dict):
                    tool_info["tool_arguments"] = arguments
                    # Look for reason parameter specifically
                    tool_info["tool_input"] = arguments.get("reason", "")
                elif isinstance(arguments, str):
                    tool_info["tool_input"] = arguments
                    try:
                        args_dict = json.loads(arguments)
                        tool_info["tool_arguments"] = args_dict
                        tool_info["tool_input"] = args_dict.get("reason", arguments)
                    except:
                        pass
                
                return tool_info  # Return on first tool_use found
            
            # Look for other formats in the content, e.g. text that mentions tool calls
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text", "")
                # Look for explicit tool call patterns in text
                if "ALLOW(" in text or "BLOCK(" in text:
                    if "ALLOW(" in text:
                        tool_info["tool_called"] = True
                        tool_info["tool_name"] = "ALLOW"
                    elif "BLOCK(" in text:
                        tool_info["tool_called"] = True
                        tool_info["tool_name"] = "BLOCK"
                    
                    # Try to extract reason (simple approach)
                    import re
                    match = re.search(r'(ALLOW|BLOCK)\(["\'](.+?)["\']\)', text)
                    if match:
                        tool_info["tool_input"] = match.group(2)
                    
                    return tool_info
    
    # Try to parse tool calls directly from content if it's a string
    if isinstance(message.content, str):
        content_str = message.content
        if "ALLOW(" in content_str or "BLOCK(" in content_str:
            if "ALLOW(" in content_str:
                tool_info["tool_called"] = True
                tool_info["tool_name"] = "ALLOW"
            elif "BLOCK(" in content_str:
                tool_info["tool_called"] = True
                tool_info["tool_name"] = "BLOCK"
            
            # Try to extract reason (simple approach)
            import re
            match = re.search(r'(ALLOW|BLOCK)\(["\'](.+?)["\']\)', content_str)
            if match:
                tool_info["tool_input"] = match.group(2)
                
            return tool_info
    
    # Check standard tool_calls attribute
    if hasattr(message, "tool_calls") and message.tool_calls:
        for tool_call in message.tool_calls:
            name = tool_call.get("name")
            if name in ["ALLOW", "BLOCK"]:
                tool_info["tool_called"] = True
                tool_info["tool_name"] = name
                # Extract arguments if available
                if "arguments" in tool_call:
                    try:
                        if isinstance(tool_call["arguments"], str):
                            args = json.loads(tool_call["arguments"])
                            tool_info["tool_input"] = args.get("reason", "")
                            tool_info["tool_arguments"] = args
                        elif isinstance(tool_call["arguments"], dict):
                            tool_info["tool_input"] = tool_call["arguments"].get("reason", "")
                            tool_info["tool_arguments"] = tool_call["arguments"]
                    except json.JSONDecodeError:
                        tool_info["tool_input"] = tool_call["arguments"]
                        
                return tool_info
    
    # Check additional_kwargs.tool_calls format (common format for anthropic)
    if hasattr(message, "additional_kwargs"):
        tool_calls = message.additional_kwargs.get("tool_calls", [])
        for tool_call in tool_calls:
            # Check function name within the tool call
            function = tool_call.get("function", {})
            name = function.get("name")
            
            if name in ["ALLOW", "BLOCK"]:
                tool_info["tool_called"] = True
                tool_info["tool_name"] = name
                
                # Try to parse arguments
                arguments = function.get("arguments", "{}")
                try:
                    args = json.loads(arguments)
                    tool_info["tool_arguments"] = args
                    tool_info["tool_input"] = args.get("reason", "")
                except:
                    tool_info["tool_input"] = arguments
                    
                return tool_info
    
    return tool_info

# Define tool executor function
# Create a ToolNode to handle tool execution
tool_node = ToolNode(superego_tools)

from langchain_core.messages import ToolMessage

# Simplified routing functions focused on the essential task

def execute_tools(state: MessagesState) -> Dict:
    """Execute ALLOW/BLOCK tools called by the superego agent."""
    print("[DEBUG] EXECUTE_TOOLS - Processing superego decision")
    
    # Let ToolNode handle tool execution
    result = tool_node.invoke(state)
    print("[DEBUG] EXECUTE_TOOLS - Decision processed")
    return result


def should_continue(state: MessagesState) -> Literal["inner_agent"] | Literal["END"]:
    """Route to inner agent only if ALLOW was called, otherwise end the flow."""
    # Check if any message in the chain is a ToolMessage with name "ALLOW"
    for message in state["messages"]:
        if isinstance(message, ToolMessage) and message.name == "ALLOW":
            print("[DEBUG] ROUTING: ALLOW tool detected -> proceeding to inner agent")
            return "inner_agent"
    
    # If we didn't find an ALLOW ToolMessage, end the flow
    print("[DEBUG] ROUTING: No ALLOW tool detected -> ending flow")
    return END

# Define superego agent prompt
superego_prompt = ChatPromptTemplate.from_messages([
    ("system", SUPEREGO_INSTRUCTIONS + "\n\n" + CONSTITUTION),
    MessagesPlaceholder(variable_name="messages")
])

# Define inner agent prompt
inner_prompt = ChatPromptTemplate.from_messages([
    ("system", INNER_AGENT_INSTRUCTIONS),
    MessagesPlaceholder(variable_name="messages")
])


def create_models():
    """Create and return the models for superego and inner agent"""
    # Configure models with streaming enabled
    superego_model = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG["streaming"],
    ).bind_tools(superego_tools)
    
    # Configure inner model with the same streaming settings
    # Ensure structured response for tool calls to be visible
    inner_model = ChatAnthropic(
        model=CONFIG["model_name"],
        streaming=CONFIG["streaming"],
    )
    
    return superego_model, inner_model

def extract_content_text(response: AIMessage) -> Tuple[Optional[str], str]:
    """Extract reasoning and full content text from an AI message."""
    reasoning = None
    full_content = ""
    
    if not hasattr(response, "content"):
        return reasoning, full_content
        
    # Extract all text content for display
    if isinstance(response.content, list):
        for item in response.content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_content = item.get("text", "")
                full_content += text_content
                if reasoning is None:  # Store first text block as primary reasoning
                    reasoning = text_content
    elif isinstance(response.content, str):
        full_content = response.content
        reasoning = response.content
    
    return reasoning, full_content

def call_superego(state: MessagesState, superego_model) -> Dict:
    """Have the superego agent evaluate a message against the constitution."""
    messages = state["messages"]
    
    # Run the superego model with ALLOW/BLOCK tools
    response = superego_model.invoke(
        superego_prompt.format(messages=messages)
    )
    
    # Simple debug output
    print(f"[DEBUG] SUPEREGO: Made a decision with tool calls: {hasattr(response, 'tool_calls')}")
    
    # Just return the updated messages - no need for complex state
    return {"messages": messages + [response]}


def inner_agent(state: MessagesState, inner_model) -> Dict:
    """Run the inner agent to respond to allowed messages."""
    messages = state["messages"]
    response = inner_model.invoke(inner_prompt.format(messages=messages))
    return {"messages": messages + [response]}

# Create a global instance of the session manager
session_manager = SessionManager()

# Import langgraph persistence class
from langgraph.checkpoint.memory import MemorySaver

# Constitution Management Functions
def get_available_constitutions() -> List[Dict[str, Any]]:
    """List all available constitutions with metadata."""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    result = []
    
    for constitution_path in constitutions_dir.glob("*.md"):
        # Get the file name without extension as the constitution ID
        constitution_id = constitution_path.stem
        
        # Read first line to extract title (assumes first line is a markdown title)
        try:
            with open(constitution_path, 'r') as f:
                first_line = f.readline().strip()
                title = first_line.replace('#', '').strip()
                
                # Get file size and last modified time
                stats = constitution_path.stat()
                
                result.append({
                    "id": constitution_id,
                    "title": title,
                    "path": str(constitution_path),
                    "size": stats.st_size,
                    "last_modified": stats.st_mtime
                })
        except Exception as e:
            # If there's an error reading the file, still include it with minimal info
            result.append({
                "id": constitution_id,
                "title": constitution_id,
                "path": str(constitution_path),
                "error": str(e)
            })
    
    # Sort by title
    result.sort(key=lambda x: x["title"])
    return result

def get_constitution_content(constitution_id: str) -> Optional[str]:
    """Get the content of a specific constitution."""
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
    """Save a constitution (create new or update existing)."""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    constitution_path = constitutions_dir / f"{constitution_id}.md"
    
    try:
        with open(constitution_path, 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False

def delete_constitution(constitution_id: str) -> bool:
    """Delete a constitution."""
    # Don't allow deleting default constitution
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
    """Set the active constitution for the application."""
    constitutions_dir = Path(CONFIG["constitutions_dir"])
    constitution_path = constitutions_dir / f"{constitution_id}.md"
    
    if not constitution_path.exists():
        return False
        
    # Update the config
    CONFIG["file_paths"]["constitution"] = str(constitution_path)
    
    # Reload instructions to ensure the new constitution is used
    global SUPEREGO_INSTRUCTIONS, CONSTITUTION, INNER_AGENT_INSTRUCTIONS
    SUPEREGO_INSTRUCTIONS, CONSTITUTION, INNER_AGENT_INSTRUCTIONS = load_instructions()
    
    # Update the superego prompt template
    global superego_prompt
    superego_prompt = ChatPromptTemplate.from_messages([
        ("system", SUPEREGO_INSTRUCTIONS + "\n\n" + CONSTITUTION),
        MessagesPlaceholder(variable_name="messages")
    ])
    
    return True

def get_active_constitution() -> str:
    """Get the currently active constitution ID."""
    constitution_path = Path(CONFIG["file_paths"]["constitution"])
    return constitution_path.stem

def create_workflow(superego_model, inner_model):
    """Create and return the workflow graph"""
    # Create graph
    workflow = StateGraph(MessagesState)
    
    # Define node functions with bound models
    def call_superego_with_model(state):
        return call_superego(state, superego_model)
    
    def inner_agent_with_model(state):
        return inner_agent(state, inner_model)
    
    # Add nodes
    workflow.add_node("superego", call_superego_with_model)
    workflow.add_node("tools", execute_tools)  # execute_tools now uses ToolNode
    workflow.add_node("inner_agent", inner_agent_with_model)
    
    # Add edges
    workflow.add_edge(START, "superego")
    workflow.add_edge("superego", "tools")
    workflow.add_conditional_edges(
        "tools",
        should_continue,
        {
            "inner_agent": "inner_agent",
            END: END
        }
    )
    workflow.add_edge("inner_agent", END)
    
    # Set entry point
    workflow.set_entry_point("superego")
    
    # Create memory-based persistence
    memory_saver = MemorySaver()
    
    # Compile workflow with persistence
    compiled = workflow.compile(checkpointer=memory_saver)
    
    return compiled

# Client API - Interface for any frontend
def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get an existing session or create a new one."""
    if session_id and session_manager.load_session(session_id):
        return session_id
    return session_manager.create_session()

def get_all_sessions() -> List[str]:
    """Get a list of all session IDs."""
    return session_manager.get_all_sessions()

def add_user_message(session_id: str, message: str) -> bool:
    """Add a user message to a session."""
    return session_manager.add_message(session_id, HumanMessage(content=message))

def get_message_history(session_id: str) -> List[Dict[str, Any]]:
    """Get the message history for a session."""
    session = session_manager.load_session(session_id)
    if not session:
        return []
    return session.messages

def run_session(session_id: str, app) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
    """Run a session and yield streaming updates."""
    session = session_manager.load_session(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Get only the last human message from our session
    last_message = None
    for msg in reversed(session.messages):
        if msg.get("type") == "HumanMessage":
            last_message = HumanMessage(content=msg.get("content", ""))
            break
    
    if not last_message:
        raise ValueError("No human message found in session")
    
    # Initial state with just the last message - LangGraph will use thread persistence
    # to load the previous messages
    state = {"messages": [last_message]}
    
    # Set up config with thread_id for persistence 
    config = {"configurable": {"thread_id": session_id}}
    
    # Try both streaming modes
    for stream_type, chunk in app.stream(state, config, stream_mode=["messages", "values"]):
        event = {
            "stream_type": stream_type,
            "timestamp": time.time()
        }
        
        # Handle message chunks (token streaming)
        if stream_type == "messages":
            message_chunk, metadata = chunk
            node_name = metadata.get("langgraph_node", "")
            
            # Extract content 
            content = ""
            if hasattr(message_chunk, "content"):
                if isinstance(message_chunk.content, str):
                    content = message_chunk.content
                elif isinstance(message_chunk.content, list):
                    for item in message_chunk.content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            content += item.get("text", "")
            
            # Add event with content
            event.update({
                "node_name": node_name,
                "content": content
            })
            
        # Handle state updates
        elif stream_type == "values":
            # Add node name to event
            node_name = chunk.get("langgraph_node")
            if node_name:
                event["node_name"] = node_name
            
            # Add tool information if available - look inside the chunk
            if node_name == "tools":
                # Check for tool_name in various formats
                tool_name = None
                tool_input = None
                
                # Direct access 
                if "tool_name" in chunk:
                    tool_name = chunk["tool_name"]
                    tool_input = chunk.get("tool_input", "")
                    
                # Check if it might be in a nested state
                elif isinstance(chunk.get("state"), dict):
                    tool_name = chunk["state"].get("tool_name")
                    tool_input = chunk["state"].get("tool_input", "")
                
                if tool_name:
                    event.update({
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_result": chunk.get("tool_result", "")
                    })
        
        # Store event in session
        session_manager.add_event(session_id, event)
        
        # Yield event for client
        yield event
    
    # Return final session state
    return session_manager.get_session_state(session_id)

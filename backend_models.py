# backend_models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal, Union

# --- Pydantic Models ---
# Aligned with frontend expectations (src/global.d.ts) and refactor_plan.md

# --- Constitution Representation ---
# Matches frontend ConfiguredConstitutionModule
class ConfiguredConstitutionModule(BaseModel):
    id: str
    title: str
    adherence_level: int = Field(..., ge=1, le=5)
    text: Optional[str] = None

# --- API Request Payloads ---
# Matches frontend RunConfig
class RunConfig(BaseModel):
    configuredModules: List[ConfiguredConstitutionModule]

# Matches frontend CheckpointConfigurable
class CheckpointConfigurable(BaseModel):
    thread_id: Optional[str] = None # String UUID or null
    runConfig: RunConfig

# Matches frontend StreamRunInput (within the overall request)
class StreamRunInput(BaseModel):
    type: Literal["human"] # Assuming only human input for now
    content: str

# Overall request body for /api/runs/stream
class StreamRunRequest(BaseModel):
    input: StreamRunInput
    configurable: CheckpointConfigurable # Use the required structure

# --- API Response Payloads ---
# Matches frontend MessageType structure (needs careful implementation in history endpoint)
# Base class (conceptual, not directly used in response model but guides implementation)
class BaseApiMessageModel(BaseModel):
    type: Literal['human', 'ai', 'system', 'tool']
    content: Any # Can be string or structured content (like tool calls)
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    additional_kwargs: Optional[Dict[str, Any]] = None

class HumanApiMessageModel(BaseApiMessageModel):
    type: Literal['human']
    content: str

class AiApiMessageModel(BaseApiMessageModel):
    type: Literal['ai']
    content: str # AI text response
    tool_calls: Optional[List[Dict[str, Any]]] = None # Matches Langchain structure
    invalid_tool_calls: Optional[List[Any]] = None

class SystemApiMessageModel(BaseApiMessageModel):
    type: Literal['system']
    content: str

class ToolApiMessageModel(BaseApiMessageModel):
    type: Literal['tool']
    content: str # Result of the tool call
    tool_call_id: str
    name: Optional[str] = None # Optional name of the tool
    is_error: Optional[bool] = None # Added to match frontend

# Union type for messages in history responses
MessageTypeModel = Union[HumanApiMessageModel, AiApiMessageModel, SystemApiMessageModel, ToolApiMessageModel]

# Matches frontend HistoryEntry
class HistoryEntry(BaseModel):
    checkpoint_id: str # Checkpoint UUID string
    thread_id: str # Thread UUID string
    values: Dict[str, Any] # Keep flexible for now, ensure 'messages' key exists
    runConfig: RunConfig # Include the RunConfig used for this entry

# --- Constitution Listing ---
# Model for listing available constitutions
class ConstitutionItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None

# --- SSE Event Data Models ---
# Aligned with frontend global.d.ts SSEEventData

class SSEThreadInfoData(BaseModel):
    thread_id: str

class SSEToolCallChunkData(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    args: Optional[str] = None

class SSEToolResultData(BaseModel):
    tool_name: str
    result: str
    is_error: bool
    tool_call_id: Optional[str] = None

class SSEEndData(BaseModel):
    thread_id: str
    checkpoint_id: Optional[str] = None # Add checkpoint_id as required by plan

class SSEEventData(BaseModel):
    type: Literal["thread_info", "chunk", "ai_tool_chunk", "tool_result", "error", "end"] # Use 'thread_info'
    node: Optional[str] = None
    thread_id: Optional[str] = None # Top-level thread_id for routing
    data: Union[SSEThreadInfoData, str, SSEToolCallChunkData, SSEToolResultData, SSEEndData, Any] # Allow Any for error data
    set_id: Optional[str] = None # For compare mode tracking (future)

# --- Old/Obsolete Models (To be removed/ignored) ---
# Define the old models here if they are still needed temporarily by other parts
# of the backend, otherwise they can be fully deleted.
# For now, let's define the ones used by the history endpoint before its refactor.
class HistoryMessage(BaseModel):
    id: str
    sender: Literal['human', 'ai', 'tool_result', 'system']
    content: Any
    timestamp: Optional[int] = None
    node: Optional[str] = None
    set_id: Optional[str] = None
    tool_name: Optional[str] = None
    is_error: Optional[bool] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class HistoryResponse(BaseModel):
    messages: List[HistoryMessage]
    thread_id: str

# backend_models.py
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# --- Pydantic Models ---
# Aligned with frontend expectations (src/global.d.ts) and refactor_plan.md

# --- Constitution Representation ---


class ConfiguredConstitutionModule(BaseModel):
    title: str
    adherence_level: int = Field(..., ge=1, le=5)
    text: Optional[str] = None
    relativePath: Optional[str] = None


# --- API Request Payloads ---


class RunConfig(BaseModel):
    configuredModules: List[ConfiguredConstitutionModule]


class CheckpointConfigurable(BaseModel):
    thread_id: Optional[str] = None  # String UUID or null
    runConfig: RunConfig


class StreamRunInput(BaseModel):
    type: Literal["human"]  # Assuming only human input for now
    content: str


class StreamRunRequest(BaseModel):
    input: StreamRunInput
    configurable: CheckpointConfigurable  # Use the required structure
    session_id: str


# --- API Response Payloads ---


class BaseApiMessageModel(BaseModel):
    type: Literal["human", "ai", "system", "tool"]
    content: Any  # Can be string or structured content (like tool calls)
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    additional_kwargs: Optional[Dict[str, Any]] = None
    nodeId: str  # Node ID is required


class HumanApiMessageModel(BaseApiMessageModel):
    type: Literal["human"]
    content: str


class AiApiMessageModel(BaseApiMessageModel):
    type: Literal["ai"]
    content: Optional[str]  # AI text response (optional if only tool calls)
    # Matches Langchain structure
    tool_calls: Optional[List[Dict[str, Any]]] = None
    invalid_tool_calls: Optional[List[Any]] = None


class SystemApiMessageModel(BaseApiMessageModel):
    type: Literal["system"]
    content: str


class ToolApiMessageModel(BaseApiMessageModel):
    type: Literal["tool"]
    content: str  # Result of the tool call
    tool_call_id: str
    name: Optional[str] = None  # Optional name of the tool
    is_error: Optional[bool] = None  # Added to match frontend


MessageTypeModel = Union[
    HumanApiMessageModel, AiApiMessageModel, SystemApiMessageModel, ToolApiMessageModel
]


class HistoryEntry(BaseModel):
    checkpoint_id: str  # Checkpoint UUID string
    thread_id: str  # Thread UUID string
    # Keep flexible for now, ensure 'messages' key exists
    values: Dict[str, Any]
    runConfig: RunConfig  # Include the RunConfig used for this entry


# --- Hierarchical Constitution Listing ---


class RemoteConstitutionMetadata(BaseModel):
    title: str
    description: Optional[str] = None
    source: Literal["remote"] = "remote"  # Fixed value
    relativePath: str  # Unique identifier, e.g., "folder/file.md"
    filename: str


class ConstitutionFolder(BaseModel):
    folderTitle: str
    relativePath: (
        str  # Path relative to constitutions dir, e.g., "folder" or "folder/subfolder"
    )
    constitutions: List[RemoteConstitutionMetadata] = Field(default_factory=list)
    subFolders: List["ConstitutionFolder"] = Field(
        default_factory=list
    )  # Forward reference


# Update the model to handle forward reference after class definition
ConstitutionFolder.model_rebuild()


class ConstitutionHierarchy(BaseModel):
    rootConstitutions: List[RemoteConstitutionMetadata] = Field(default_factory=list)
    rootFolders: List[ConstitutionFolder] = Field(default_factory=list)


# --- SSE Event Data Models ---
# Aligned with frontend global.d.ts SSEEventData

# SSEThreadInfoData removed as run_start contains the thread_id


class SSEChunkData(BaseModel):
    node: str
    content: str


class SSEToolCallChunkData(BaseModel):
    node: str
    id: Optional[str] = None
    name: Optional[str] = None
    args: Optional[str] = None


class SSEToolResultData(BaseModel):
    node: str
    tool_name: str
    content: str
    is_error: bool
    tool_call_id: Optional[str] = None


class SSEErrorData(BaseModel):
    node: str
    error: str


class SSEEndData(BaseModel):
    node: str
    thread_id: str
    checkpoint_id: Optional[str] = None


class SSERunStartData(BaseModel):
    thread_id: str
    runConfig: RunConfig
    initialMessages: List[MessageTypeModel]
    node: str


class SSEEventData(BaseModel):
    type: Literal["run_start", "chunk", "ai_tool_chunk", "tool_result", "error", "end"]
    thread_id: Optional[str] = None
    data: Union[
        SSERunStartData,
        SSEChunkData,
        SSEToolCallChunkData,
        SSEToolResultData,
        SSEErrorData,
        SSEEndData,
    ]

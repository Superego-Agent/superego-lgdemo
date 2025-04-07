# src/backend_server_async.py

# Standard library imports
import os
import uuid
import json
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Literal, Union, AsyncGenerator, Tuple
from datetime import datetime # Added for timestamp handling in models

# Third-party imports
import aiosqlite # Keep for potential direct interaction if needed, though manager preferred
from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# Langchain/Langgraph specific imports
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import CheckpointTuple, BaseCheckpointSaver # Import BaseCheckpointSaver for type hint

# Project-specific imports
try:
    from config import CONFIG # Assumed to exist and be configured
    from constitution_utils import get_available_constitutions, get_combined_constitution_content # Assumed to exist
    from superego_core_async import create_models, create_workflow # Assumed to exist
    # Removed metadata_manager import
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Ensure backend_server_async.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH.")
    import sys
    sys.exit(1)

# --- Globals ---
graph_app: Any = None
checkpointer: Optional[BaseCheckpointSaver] = None # Use BaseCheckpointSaver hint
inner_agent_app: Any = None

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown logic."""
    global graph_app, checkpointer, inner_agent_app
    print("Backend server starting up...")
    try:
        # Removed metadata_manager.init_db()

        # Load models and create workflow (which initializes checkpointer)
        superego_model, inner_model = create_models()
        graph_app, checkpointer, inner_agent_app = await create_workflow(
            superego_model=superego_model,
            inner_model=inner_model
        )
        # Langgraph's SqliteSaver manages its own connection lifecycle internally
        # typically, but good practice to ensure it's handled if exposed.
        # However, create_workflow now returns the checkpointer instance directly.

        if not checkpointer:
             print("Warning: Checkpointer was not initialized during startup.")
        if not graph_app:
             print("Warning: Main graph app was not initialized.")
        if not inner_agent_app:
             print("Warning: Inner agent app was not initialized.")


        print("Models, graph, and databases initialized successfully.")
    except Exception as e:
        print(f"FATAL: Error during startup: {e}")
        traceback.print_exc()
        raise RuntimeError("Failed to initialize backend components") from e

    yield # Application runs here

    # --- Shutdown ---
    print("Backend server shutting down...")
    # No explicit connection closing needed here if using `async with`
    # within metadata_manager functions and LangGraph manages its checkpointer conn.
    # If checkpointer connection was manually created/passed, close it here.
    if checkpointer and isinstance(checkpointer, AsyncSqliteSaver) and checkpointer.conn:
         try:
              print("Attempting to close checkpointer DB connection...")
              await checkpointer.conn.close()
              print("Checkpointer DB connection closed.")
         except Exception as e:
              print(f"Warning: Error closing checkpointer connection: {e}")

# --- FastAPI App ---
app = FastAPI(title="Superego Backend", lifespan=lifespan)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
# Ensure these match frontend expectations (src/global.d.ts)

class ConstitutionItem(BaseModel):
    id: str
    name: str
    description: Optional[str] = None

# ThreadItem and RenameThreadRequest removed - managed by frontend localStorage

class HistoryMessage(BaseModel):
    id: str # Unique ID for the message within its history context
    sender: Literal['human', 'ai', 'tool_result', 'system']
    content: Any # Allow flexibility, will be serialized
    timestamp: Optional[int] = None
    node: Optional[str] = None
    set_id: Optional[str] = None # Keep for compare mode differentiation in frontend
    tool_name: Optional[str] = None
    is_error: Optional[bool] = None

class HistoryResponse(BaseModel):
    messages: List[HistoryMessage]
    thread_id: str # The checkpoint thread ID (string UUID)
    # thread_name is removed - managed by frontend

class StreamRunInput(BaseModel):
    type: Literal["human"]
    content: str

class StreamRunRequest(BaseModel):
    # Now uses the string checkpoint thread ID (UUID)
    thread_id: Optional[str] = None
    input: StreamRunInput
    constitution_ids: List[str] = ["none"]

class CompareRunSet(BaseModel):
    id: str # User-defined ID for the set (e.g., 'strict_vs_default')
    constitution_ids: List[str]

class CompareRunRequest(BaseModel):
    # Now uses the string checkpoint thread ID (UUID)
    thread_id: Optional[str] = None
    input: StreamRunInput
    constitution_sets: List[CompareRunSet]


# SSE Event Data Models (matching global.d.ts SSEEventData)
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
    # Represents the checkpoint thread ID (string UUID) this run used/created
    thread_id: str

class SSEEventData(BaseModel):
    type: Literal["chunk", "ai_tool_chunk", "tool_result", "error", "end"]
    node: Optional[str] = None
    data: Union[str, SSEToolCallChunkData, SSEToolResultData, SSEEndData]
    set_id: Optional[str] = None # For compare mode tracking

# --- Helper Function for Standard Streaming ---
async def stream_events(
    checkpoint_thread_id: str, # The unique checkpoint ID (string UUID) for this specific run
    input_messages: List[BaseMessage],
    constitution_ids: List[str],
    run_app: Any, # The compiled LangGraph app to run
    set_id: Optional[str] = None # Identifier for compare mode sets
) -> AsyncGenerator[ServerSentEvent, None]:
    """Generates Server-Sent Events for a single LangGraph run."""
    if not run_app or not checkpointer:
        error_data = "Graph app or checkpointer not initialized."
        yield ServerSentEvent(data=SSEEventData(type="error", node="setup", data=error_data, set_id=set_id).model_dump_json())
        return

    current_node_name: Optional[str] = None
    last_yielded_text: Dict[Tuple[Optional[str], Optional[str]], str] = {}
    # run_id_for_db removed

    try:
        # Removed metadata_manager.add_run call

        # Load constitution content
        constitution_content_for_run, loaded_ids = get_combined_constitution_content(constitution_ids)
        requested_set = set(id for id in constitution_ids if id != "none")
        missing_in_run = requested_set - set(loaded_ids)
        if missing_in_run:
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="setup", # Use 'error' type for warnings too? Or add 'warning' type?
                data=f"Warning: Constitution(s) not found/loaded: {', '.join(missing_in_run)}. Running without.",
                set_id=set_id
            ).model_dump_json())


        # Prepare run config using the UNIQUE checkpoint_thread_id for this run
        config = {"configurable": {"thread_id": checkpoint_thread_id, "constitution_content": constitution_content_for_run}}
        stream_input = {'messages': input_messages}

        # Stream events from the LangGraph app
        stream = run_app.astream_events(stream_input, config=config, version="v1")

        async for event in stream:
            event_type = event.get("event")
            event_name = event.get("name")
            tags = event.get("tags", [])
            event_data = event.get("data", {})

            # --- Track Current Node ---
            potential_node_tags = [tag for tag in tags if tag in ["superego", "inner_agent", "tools"]]
            if event_name in ["superego", "inner_agent", "tools"]:
                 current_node_name = event_name
            elif potential_node_tags:
                 current_node_name = potential_node_tags[-1] # Use the last relevant tag found

            yield_key = (current_node_name, set_id) # Key for deduplicating text chunks

            # --- Process Different Event Types ---
            # (Chunk, Tool Chunk, Tool Result processing logic remains largely the same as before)
            # Text Chunk Events
            if event_type == "on_chat_model_stream" and isinstance(event_data.get("chunk"), AIMessageChunk):
                chunk: AIMessageChunk = event_data["chunk"]
                text_content = ""
                if isinstance(chunk.content, str):
                    text_content = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_content += item.get("text", "")
                            elif item.get("type") == "content_block_delta" and item.get("delta", {}).get("type") == "text_delta":
                                 text_content += item.get("delta", {}).get("text", "")

                if text_content:
                    last_text = last_yielded_text.get(yield_key, "")
                    if text_content != last_text:
                        sse_payload_text = SSEEventData(type="chunk", node=current_node_name, data=text_content, set_id=set_id)
                        yield ServerSentEvent(data=sse_payload_text.model_dump_json())
                        last_yielded_text[yield_key] = text_content

            # Tool Call Chunk Events
            elif event_type == "on_chat_model_stream" and isinstance(event_data.get("chunk"), AIMessageChunk): # Need elif if combined
                 chunk: AIMessageChunk = event_data["chunk"]
                 tool_chunks = getattr(chunk, 'tool_call_chunks', [])
                 if tool_chunks:
                     for tc_chunk in tool_chunks:
                         chunk_data = SSEToolCallChunkData(
                             id=tc_chunk.get("id"),
                             name=tc_chunk.get("name"),
                             args=tc_chunk.get("args")
                         )
                         sse_payload_tool = SSEEventData(type="ai_tool_chunk", node=current_node_name, data=chunk_data, set_id=set_id)
                         yield ServerSentEvent(data=sse_payload_tool.model_dump_json())


            # Tool Result Events
            elif event_type == "on_tool_end":
                 tool_output = event_data.get("output")
                 try:
                      output_str = json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output
                 except Exception:
                      output_str = str(tool_output)

                 tool_func_name = event.get("name")
                 is_error = isinstance(tool_output, Exception)
                 tool_call_id = None
                 parent_ids = event_data.get("parent_run_ids")
                 if isinstance(parent_ids, list):
                      possible_ids = [pid for pid in parent_ids if isinstance(pid, str)]
                      if possible_ids:
                         tool_call_id = possible_ids[-1]

                 sse_payload_data = SSEToolResultData(
                     tool_name=tool_func_name or "unknown_tool",
                     result=output_str,
                     is_error=is_error,
                     tool_call_id=tool_call_id
                 )
                 sse_payload = SSEEventData(type="tool_result", node="tools", data=sse_payload_data, set_id=set_id)
                 yield ServerSentEvent(data=sse_payload.model_dump_json())

        # --- Stream End ---
        # Pass the checkpoint_thread_id (string UUID) back to the frontend
        yield ServerSentEvent(data=SSEEventData(type="end", node=current_node_name or "graph", data=SSEEndData(thread_id=checkpoint_thread_id), set_id=set_id).model_dump_json())

        # Removed post-stream checkpoint update logic related to metadata DB

    except Exception as e:
        print(f"Stream Error (Checkpoint Thread: {checkpoint_thread_id}, Set: {set_id}): {e}")
        traceback.print_exc()
        try:
            error_data = f"Streaming error: {str(e)}"
            # Ensure checkpoint_thread_id is sent even in error/end events
            yield ServerSentEvent(data=SSEEventData(type="error", node=current_node_name or "graph", data=error_data, set_id=set_id).model_dump_json())
            yield ServerSentEvent(data=SSEEventData(type="end", node="error", data=SSEEndData(thread_id=checkpoint_thread_id), set_id=set_id).model_dump_json()) # Send end on error too
        except Exception as inner_e:
            print(f"Failed to send stream error event: {inner_e}")


# --- API Endpoints ---

@app.get("/api/constitutions", response_model=List[ConstitutionItem])
async def get_constitutions_endpoint():
    """Returns a list of available constitutions."""
    # (No changes needed to this endpoint's logic)
    try:
        constitutions_dict = get_available_constitutions()
        if "none" not in constitutions_dict:
             constitutions_dict["none"] = {"name": "None", "description": "No constitution applied."}
        elif not isinstance(constitutions_dict.get("none"), dict):
              constitutions_dict["none"] = {"name": "None", "description": str(constitutions_dict.get("none", "N/A"))}

        response_items = []
        for k, v in constitutions_dict.items():
              if isinstance(v, dict):
                   response_items.append(ConstitutionItem(
                        id=k,
                        name=v.get('name', k.replace('_', ' ').title()),
                        description=v.get('description')
                   ))
              else:
                   print(f"Warning: Constitution '{k}' has non-dictionary value: {v}. Skipping.")
        return response_items
    except Exception as e:
        print(f"Error loading constitutions: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load constitutions: {str(e)}")

# Removed /api/threads and /api/threads/{thread_id}/rename endpoints

@app.get("/api/threads/{thread_id}/history", response_model=HistoryResponse)
async def get_thread_history_endpoint(
    thread_id: str = FastApiPath(..., title="The checkpoint thread ID (UUID string)")
):
    """Retrieves the message history for a specific checkpoint thread ID."""
    if not checkpointer:
        print("Error: Checkpointer not available for getting history.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    try:
        # Directly use the provided string thread_id with the checkpointer
        print(f"Fetching history using Checkpoint Thread ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple: Optional[CheckpointTuple] = await checkpointer.aget_tuple(config)

        # Process messages from the checkpoint tuple
        history_messages: List[HistoryMessage] = []
        if not checkpoint_tuple:
             print(f"No checkpoint found for thread_id: {thread_id}")
             # Return empty history but indicate the requested thread_id
             return HistoryResponse(messages=[], thread_id=thread_id)

        if checkpoint_tuple and checkpoint_tuple.checkpoint:
             messages_from_state = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
             # ... (message processing logic - human, ai, tool - copied from previous version) ...
             # --- Timestamp Handling ---
             ts_value = checkpoint_tuple.checkpoint.get("ts")
             base_timestamp_ms = None
             if ts_value and hasattr(ts_value, 'timestamp') and callable(ts_value.timestamp):
                  try:
                     base_timestamp_ms = int(ts_value.timestamp() * 1000)
                  except (TypeError, ValueError) as ts_err:
                      print(f"Warning: Could not convert timestamp '{ts_value}' ({type(ts_value)}) to UNIX ms for thread {thread_id}: {ts_err}")

             # --- Message Loop ---
             for i, msg in enumerate(messages_from_state):
                 sender: Optional[Literal['human', 'ai', 'tool_result', 'system']] = None
                 node: Optional[str] = None
                 formatted_content: Optional[str] = None
                 tool_name: Optional[str] = None
                 is_error: Optional[bool] = None

                 if isinstance(msg, HumanMessage):
                     sender = "human"
                     node = getattr(msg, 'name', None)
                     formatted_content = str(msg.content) if msg.content is not None else ""
                 elif isinstance(msg, AIMessage):
                     sender = "ai"
                     node = getattr(msg, 'name', 'ai')
                     raw_content = msg.content
                     content_str = ""
                     if isinstance(raw_content, list):
                         for item in raw_content:
                             if isinstance(item, dict) and item.get("type") == "text":
                                 content_str += item.get("text", "")
                     elif isinstance(raw_content, str): content_str = raw_content
                     elif raw_content is not None: content_str = str(raw_content)

                     tool_calls_str = ""
                     if tool_calls := getattr(msg, "tool_calls", None):
                         tool_calls_str = "\n".join([
                             f"-> Called Tool: {tc.get('name', 'N/A')}({json.dumps(tc.get('args', {}))})"
                             for tc in tool_calls if isinstance(tc, dict)
                         ])

                     if content_str and tool_calls_str: formatted_content = f"{content_str}\n{tool_calls_str}"
                     elif content_str: formatted_content = content_str
                     elif tool_calls_str: formatted_content = tool_calls_str
                     else: formatted_content = ""
                 elif isinstance(msg, ToolMessage):
                     sender = "tool_result"
                     node = "tools"
                     tool_name = getattr(msg, 'name', 'unknown_tool')
                     is_error = isinstance(msg.content, Exception)
                     if isinstance(msg.content, str): formatted_content = msg.content
                     elif msg.content is None: formatted_content = ""
                     else:
                         try: formatted_content = json.dumps(msg.content)
                         except TypeError: formatted_content = str(msg.content)

                 if sender and formatted_content is not None:
                     msg_timestamp = base_timestamp_ms + i if base_timestamp_ms is not None else None
                     history_messages.append(HistoryMessage(
                         id=f"{thread_id}-{i}", # Use checkpoint ID (thread_id) in message ID
                         sender=sender,
                         content=formatted_content,
                         timestamp=msg_timestamp,
                         node=node,
                         tool_name=tool_name,
                         is_error=is_error,
                         # set_id is not typically stored in checkpoint messages, omit or derive if needed
                     ))
             # --- End Message Loop ---

        # Return history with the string thread_id used for lookup
        return HistoryResponse(messages=history_messages, thread_id=thread_id)

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
        print(f"Error getting history for thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load history.")

# --- Run Endpoints ---

@app.post("/api/runs/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    """Handles streaming runs for a single thread (normal chat)."""
    checkpoint_thread_id = request.thread_id # This is the string UUID or None

    try:
        # 1. Determine the checkpoint thread ID to use
        if checkpoint_thread_id is None:
            # Generate a new UUID for this run's checkpoint thread
            checkpoint_thread_id = str(uuid.uuid4())
            print(f"Received request for new thread. Generated Checkpoint Thread ID: {checkpoint_thread_id}")
        else:
            # Use the provided checkpoint thread ID
            print(f"Received request to continue Checkpoint Thread ID: {checkpoint_thread_id}")
            # Optional: Could verify if a checkpoint exists for this ID, but LangGraph handles it.

        # 2. Prepare input messages
        if not request.input or not request.input.content:
             raise HTTPException(status_code=400, detail="Input content is required to start a stream.")
        input_messages = [HumanMessage(content=request.input.content)]

        # 3. Return the SSE response stream
        # Pass the determined checkpoint_thread_id to the helper
        return EventSourceResponse(stream_events(
            checkpoint_thread_id=checkpoint_thread_id,
            input_messages=input_messages,
            constitution_ids=request.constitution_ids,
            run_app=graph_app # Use the main graph app
        ))

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
         print(f"Error setting up stream run for thread {request.thread_id}: {e}")
         traceback.print_exc()
         # Return an error response instead of EventSourceResponse if setup fails
         raise HTTPException(status_code=500, detail="Failed to initiate stream.")


# --- Compare Streaming Helper and Endpoint ---

# --- Compare Streaming Helper and Endpoint ---

# consume_and_forward_stream helper remains the same

async def stream_compare_events(
    base_checkpoint_thread_id: Optional[str], # The base thread ID (UUID string) or None if new
    input_message: BaseMessage,
    constitution_sets: List[CompareRunSet], # Use the Pydantic model directly
    include_inner_agent_only: bool = True # Flag to control inner agent run
) -> AsyncGenerator[ServerSentEvent, None]:
    """Runs multiple streams concurrently for comparison and multiplexes their events."""
    event_queue = asyncio.Queue()
    consumer_tasks = []
    runs_to_perform: List[Tuple[str, List[str], str, Any]] = [] # (checkpoint_thread_id, constitution_ids, set_id, run_app)

    # Generate a unique group ID for this comparison operation
    compare_group_id = str(uuid.uuid4())

    # Determine base thread ID for naming/grouping checkpoints
    # If starting a new comparison, generate a base UUID, otherwise use the provided one
    effective_base_thread_id = base_checkpoint_thread_id or str(uuid.uuid4())
    is_new_comparison_thread = base_checkpoint_thread_id is None
    print(f"Compare: Base Checkpoint Thread ID: {effective_base_thread_id} (New: {is_new_comparison_thread})")

    # Prepare Superego-involved runs
    for const_set in constitution_sets:
        set_id = const_set.id
        # Create a unique checkpoint ID for this specific run within the comparison
        checkpoint_thread_id = f"compare_{effective_base_thread_id}_{set_id}"
        runs_to_perform.append(
            (checkpoint_thread_id, const_set.constitution_ids, set_id, graph_app)
        )

    # Prepare Inner Agent Only run (if applicable)
    if include_inner_agent_only and inner_agent_app:
        inner_set_id = "inner_agent_only"
        inner_checkpoint_thread_id = f"compare_{effective_base_thread_id}_{inner_set_id}"
        runs_to_perform.append(
            (inner_checkpoint_thread_id, [], inner_set_id, inner_agent_app)
        )
    elif include_inner_agent_only:
         print("Warning: Inner agent app not available, skipping inner_agent_only comparison run.")

    active_stream_count = len(runs_to_perform)
    print(f"Compare: Starting {active_stream_count} parallel runs based on Thread ID: {effective_base_thread_id}")

    # Launch consumer tasks
    for checkpoint_thread_id, constitution_ids, set_id, run_app in runs_to_perform:
        print(f"Compare: Launching Set='{set_id}', Checkpoint Thread='{checkpoint_thread_id}'")
        stream = stream_events(
            checkpoint_thread_id=checkpoint_thread_id, # Pass the unique checkpoint ID for this run
            input_messages=[input_message],
            constitution_ids=constitution_ids,
            run_app=run_app,
            set_id=set_id # Pass set_id for frontend tracking
        )
        task = asyncio.create_task(consume_and_forward_stream(stream, event_queue))
        consumer_tasks.append(task)

    # Multiplex events from the queue
    finished_streams = 0
    while finished_streams < active_stream_count:
        try:
            event = await event_queue.get()
            if event is None:
                finished_streams += 1
                continue
            yield event
            event_queue.task_done()
        except asyncio.CancelledError:
             print("Compare event streaming cancelled.")
             break
        except Exception as e:
            print(f"Error processing compare event queue: {e}")
            # Yield a generic error for the comparison itself
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="compare_multiplexer", data=f"Compare error: {e}"
            ).model_dump_json())
            # Signal end with the *base* thread ID so frontend knows the overall operation ended
            yield ServerSentEvent(data=SSEEventData(
                type="end", node="error", data=SSEEndData(thread_id=effective_base_thread_id)
            ).model_dump_json())


    print(f"Compare streaming finished for base Thread ID {effective_base_thread_id}.")
    for task in consumer_tasks:
         if not task.done(): task.cancel()
    await asyncio.gather(*consumer_tasks, return_exceptions=True)


@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(request: CompareRunRequest):
    """Handles streaming runs for comparing multiple constitution sets."""
    base_checkpoint_thread_id = request.thread_id # String UUID or None

    try:
        # 1. Validate input
        if not request.input or not request.input.content:
             raise HTTPException(status_code=400, detail="Input content is required for comparison.")
        # Allow empty constitution_sets if inner_agent_app exists
        if not request.constitution_sets and not inner_agent_app:
             raise HTTPException(status_code=400, detail="At least one constitution set (or inner agent) is required for comparison.")

        # 2. Prepare input message
        input_message = HumanMessage(content=request.input.content)

        # 3. Return the SSE response stream
        return EventSourceResponse(stream_compare_events(
            base_checkpoint_thread_id=base_checkpoint_thread_id,
            input_message=input_message,
            constitution_sets=request.constitution_sets,
            include_inner_agent_only=True # Assuming we always want inner agent if available
        ))

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
         print(f"Error setting up compare run for thread {request.thread_id}: {e}")
         traceback.print_exc()
         raise HTTPException(status_code=500, detail="Failed to initiate comparison stream.")


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY environment variable not set. LangGraph models may fail.")

    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    reload = os.getenv("BACKEND_RELOAD", "true").lower() == "true"

    print(f"Starting Uvicorn server on {host}:{port} (Reload: {'enabled' if reload else 'disabled'})")
    uvicorn.run(
        "backend_server_async:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

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
    # Import the new metadata manager
    import metadata_manager
    from metadata_manager import _generate_default_thread_name # Import helper if needed directly
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
        # Initialize metadata database first
        await metadata_manager.init_db()

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

# Updated ThreadItem to reflect metadata DB structure
class ThreadItem(BaseModel):
    thread_id: int # Now the integer ID from metadata DB
    name: str
    last_updated: Optional[datetime] = None # Use datetime for potential sorting/display

class RenameThreadRequest(BaseModel):
    new_name: str

class HistoryMessage(BaseModel):
    id: str
    sender: Literal['human', 'ai', 'tool_result', 'system']
    content: Any # Allow flexibility, will be serialized
    timestamp: Optional[int] = None
    node: Optional[str] = None
    set_id: Optional[str] = None # Keep for compare mode differentiation in frontend
    tool_name: Optional[str] = None
    is_error: Optional[bool] = None

class HistoryResponse(BaseModel):
    messages: List[HistoryMessage]
    thread_id: int # The metadata thread ID
    thread_name: Optional[str] = None # Add name for context

# NewThreadResponse is no longer needed as threads are created implicitly

class StreamRunInput(BaseModel):
    type: Literal["human"]
    content: str

class StreamRunRequest(BaseModel):
    # Now uses the integer metadata thread ID
    thread_id: Optional[int] = None
    input: StreamRunInput # Input is now required to start a run
    constitution_ids: List[str] = ["none"]

class CompareRunSet(BaseModel):
    id: str # User-defined ID for the set (e.g., 'strict_vs_default')
    constitution_ids: List[str]

class CompareRunRequest(BaseModel):
    # Now uses the integer metadata thread ID
    thread_id: Optional[int] = None
    input: StreamRunInput # Compare runs always need an input
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
    # Represents the metadata thread ID this run belongs to
    thread_id: int

class SSEEventData(BaseModel):
    type: Literal["chunk", "ai_tool_chunk", "tool_result", "error", "end"]
    node: Optional[str] = None
    data: Union[str, SSEToolCallChunkData, SSEToolResultData, SSEEndData]
    set_id: Optional[str] = None # For compare mode tracking

# --- Helper Function for Standard Streaming ---
async def stream_events(
    metadata_thread_id: int, # The ID from our threads table
    checkpoint_thread_id: str, # The unique ID for this specific run's checkpoints
    input_messages: List[BaseMessage], # Input is required now
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
    run_id_for_db: Optional[int] = None # Store the run_id if we add it

    try:
        # Add run entry to metadata DB before starting
        # Note: If this fails, the stream won't start. Consider error handling.
        run_id_for_db = await metadata_manager.add_run(
            parent_thread_id=metadata_thread_id,
            checkpoint_thread_id=checkpoint_thread_id,
            constitution_ids=constitution_ids,
            compare_group_id=set_id # Use set_id as compare_group_id if present
        )
        print(f"DB Run {run_id_for_db}: Added for Checkpoint Thread {checkpoint_thread_id} (Parent: {metadata_thread_id})")


        # Load constitution content
        constitution_content_for_run, loaded_ids = get_combined_constitution_content(constitution_ids)
        # ... (rest of constitution loading and warning logic remains the same) ...
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
        # Pass the metadata_thread_id back to the frontend
        yield ServerSentEvent(data=SSEEventData(type="end", node=current_node_name or "graph", data=SSEEndData(thread_id=metadata_thread_id), set_id=set_id).model_dump_json())

        # --- Post-Stream: Update final checkpoint ID (Optional - deferred) ---
        # try:
        #      final_checkpoint_tuple = await checkpointer.aget_tuple(config) # Get latest for this run
        #      if final_checkpoint_tuple and final_checkpoint_tuple.checkpoint:
        #           final_checkpoint_id = final_checkpoint_tuple.checkpoint.get("id") # Assuming ID is in checkpoint structure
        #           if final_checkpoint_id and run_id_for_db:
        #                await metadata_manager.update_run_final_checkpoint(run_id_for_db, final_checkpoint_id)
        #                print(f"DB Run {run_id_for_db}: Updated final checkpoint ID to {final_checkpoint_id}")
        # except Exception as cp_err:
        #      print(f"Warning: Failed to get/update final checkpoint ID for run {run_id_for_db}: {cp_err}")


    except Exception as e:
        print(f"Stream Error (Metadata Thread: {metadata_thread_id}, Checkpoint Thread: {checkpoint_thread_id}, Set: {set_id}): {e}")
        traceback.print_exc()
        try:
            error_data = f"Streaming error: {str(e)}"
            # Ensure metadata_thread_id is sent even in error/end events
            yield ServerSentEvent(data=SSEEventData(type="error", node=current_node_name or "graph", data=error_data, set_id=set_id).model_dump_json())
            yield ServerSentEvent(data=SSEEventData(type="end", node="error", data=SSEEndData(thread_id=metadata_thread_id), set_id=set_id).model_dump_json()) # Send end on error too
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

# --- Thread Endpoints (using Metadata DB) ---

@app.get("/api/threads", response_model=List[ThreadItem])
async def get_threads_endpoint():
    """Lists threads from the metadata database."""
    try:
        threads_data = await metadata_manager.list_threads()
        # Map DB data to Pydantic model, converting datetime if needed
        return [
            ThreadItem(
                thread_id=t['thread_id'],
                name=t['name'],
                last_updated=t['last_updated'] # Assumes DB returns datetime compatible type
            ) for t in threads_data
        ]
    except Exception as e:
        print(f"Error listing threads from metadata DB: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to list threads.")

@app.put("/api/threads/{thread_id}/rename")
async def rename_thread_endpoint(
    thread_id: int = FastApiPath(..., title="The metadata ID of the thread to rename"),
    request: RenameThreadRequest = Body(...)
):
    """Renames a thread in the metadata database."""
    if not request.new_name or len(request.new_name.strip()) == 0:
         raise HTTPException(status_code=400, detail="New name cannot be empty.")
    try:
        # Check if thread exists first (optional, rename is idempotent if it doesn't)
        thread_info = await metadata_manager.get_thread(thread_id)
        if not thread_info:
            raise HTTPException(status_code=404, detail=f"Thread with ID {thread_id} not found.")

        await metadata_manager.rename_thread(thread_id, request.new_name.strip())
        print(f"Thread {thread_id} renamed to '{request.new_name.strip()}'")
        # Return the updated thread info
        updated_thread = await metadata_manager.get_thread(thread_id)
        if updated_thread:
             # Map to ThreadItem before returning
             return ThreadItem(
                 thread_id=updated_thread['thread_id'],
                 name=updated_thread['name'],
                 last_updated=updated_thread['last_updated']
             )
        else:
             # Should not happen if rename succeeded, but handle defensively
             raise HTTPException(status_code=500, detail="Failed to retrieve thread info after rename.")
    except HTTPException:
        raise # Re-raise explicit HTTP exceptions
    except Exception as e:
        print(f"Error renaming thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to rename thread.")


@app.get("/api/threads/{thread_id}/history", response_model=HistoryResponse)
async def get_thread_history_endpoint(
    thread_id: int = FastApiPath(..., title="The metadata ID of the thread")
):
    """Retrieves the message history for the LATEST run of a given thread."""
    if not checkpointer:
        print("Error: Checkpointer not available for getting history.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    try:
        # 1. Get thread details from metadata DB for context
        thread_info = await metadata_manager.get_thread(thread_id)
        if not thread_info:
            raise HTTPException(status_code=404, detail=f"Thread with ID {thread_id} not found.")
        thread_name = thread_info.get('name')

        # 2. Find the checkpoint_thread_id for the most recent run of this thread
        latest_checkpoint_thread_id = await metadata_manager.get_latest_checkpoint_thread_id(thread_id)

        if not latest_checkpoint_thread_id:
            print(f"No runs found for thread {thread_id}. Returning empty history.")
            return HistoryResponse(messages=[], thread_id=thread_id, thread_name=thread_name)

        print(f"Fetching history for Thread {thread_id} using latest Checkpoint Thread ID: {latest_checkpoint_thread_id}")

        # 3. Use checkpointer to get the state tuple for that specific checkpoint thread
        config = {"configurable": {"thread_id": latest_checkpoint_thread_id}}
        checkpoint_tuple: Optional[CheckpointTuple] = await checkpointer.aget_tuple(config)

        # 4. Process messages from the checkpoint tuple (logic remains the same as before)
        history_messages: List[HistoryMessage] = []
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
                         id=f"{latest_checkpoint_thread_id}-{i}", # Use checkpoint ID in message ID
                         sender=sender,
                         content=formatted_content,
                         timestamp=msg_timestamp,
                         node=node,
                         tool_name=tool_name,
                         is_error=is_error,
                     ))
             # --- End Message Loop ---

        return HistoryResponse(messages=history_messages, thread_id=thread_id, thread_name=thread_name)

    except HTTPException: # Re-raise validation or explicit HTTP errors
        raise
    except Exception as e:
        print(f"Error getting history for thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load history.")

# --- Run Endpoints ---

@app.post("/api/runs/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    """Handles streaming runs for a single thread (normal chat)."""
    metadata_thread_id = request.thread_id
    run_id_in_db: Optional[int] = None

    try:
        # 1. Ensure we have a metadata thread ID
        if metadata_thread_id is None:
            # Create a new thread in the metadata DB
            default_name = _generate_default_thread_name(request.constitution_ids)
            metadata_thread_id = await metadata_manager.add_thread(name=default_name)
            print(f"Implicitly created new Thread {metadata_thread_id} with default name: '{default_name}'")
        else:
            # Verify the provided thread ID exists (optional but good practice)
            thread_info = await metadata_manager.get_thread(metadata_thread_id)
            if not thread_info:
                 raise HTTPException(status_code=404, detail=f"Thread with ID {metadata_thread_id} not found.")

        # 2. Generate a unique checkpoint_thread_id for this specific run
        checkpoint_thread_id = f"thread_{metadata_thread_id}_run_{uuid.uuid4()}"
        print(f"Starting stream run for Thread {metadata_thread_id}, Checkpoint Thread ID: {checkpoint_thread_id}")

        # 3. Prepare input messages
        if not request.input or not request.input.content:
             # Input is now required according to model, but double-check
             raise HTTPException(status_code=400, detail="Input content is required to start a stream.")
        input_messages = [HumanMessage(content=request.input.content)]

        # 4. Return the SSE response stream
        # The stream_events helper now handles adding the run to the DB
        return EventSourceResponse(stream_events(
            metadata_thread_id=metadata_thread_id,
            checkpoint_thread_id=checkpoint_thread_id,
            input_messages=input_messages,
            constitution_ids=request.constitution_ids,
            run_app=graph_app # Use the main graph app
        ))

    except HTTPException:
        raise
    except Exception as e:
         print(f"Error setting up stream run for thread {request.thread_id}: {e}")
         traceback.print_exc()
         # Return an error response instead of EventSourceResponse if setup fails
         raise HTTPException(status_code=500, detail="Failed to initiate stream.")


# --- Compare Streaming Helper and Endpoint ---

async def consume_and_forward_stream(
    stream: AsyncGenerator[ServerSentEvent, None],
    queue: asyncio.Queue
):
    """Consumes events from a stream and puts them onto a shared queue."""
    # (No changes needed in this helper)
    try:
        async for event in stream:
            await queue.put(event)
    except Exception as e:
        print(f"Error consuming stream: {e}")
        error_event = ServerSentEvent(data=SSEEventData(type="error", node="compare_consumer", data=f"Stream consumption error: {e}").model_dump_json())
        await queue.put(error_event)
    finally:
        await queue.put(None)


async def stream_compare_events(
    metadata_thread_id: int, # The parent metadata thread ID
    input_message: BaseMessage,
    runs_to_perform: List[Tuple[str, List[str], str, Any]] # List of (checkpoint_thread_id, constitution_ids, set_id, run_app)
) -> AsyncGenerator[ServerSentEvent, None]:
    """Runs multiple streams concurrently for comparison and multiplexes their events."""
    event_queue = asyncio.Queue()
    consumer_tasks = []
    active_stream_count = len(runs_to_perform)

    print(f"Compare: Starting {active_stream_count} parallel runs for Thread {metadata_thread_id}")

    for checkpoint_thread_id, constitution_ids, set_id, run_app in runs_to_perform:
        print(f"Compare: Launching Set='{set_id}', Checkpoint Thread='{checkpoint_thread_id}'")
        stream = stream_events(
            metadata_thread_id=metadata_thread_id, # Pass parent ID for SSE end event
            checkpoint_thread_id=checkpoint_thread_id, # Unique ID for this specific run
            input_messages=[input_message],
            constitution_ids=constitution_ids,
            run_app=run_app,
            set_id=set_id # Pass set_id for frontend tracking
        )
        task = asyncio.create_task(consume_and_forward_stream(stream, event_queue))
        consumer_tasks.append(task)

    # --- Multiplex events from the queue ---
    # (No changes needed in multiplexing logic)
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
            # Ensure metadata_thread_id is sent even in error/end events
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="compare_multiplexer", data=f"Compare error: {e}"
            ).model_dump_json())
            yield ServerSentEvent(data=SSEEventData(
                type="end", node="error", data=SSEEndData(thread_id=metadata_thread_id)
            ).model_dump_json()) # Signal end


    print(f"Compare streaming finished for Thread {metadata_thread_id}.")
    for task in consumer_tasks:
         if not task.done(): task.cancel()
    await asyncio.gather(*consumer_tasks, return_exceptions=True)


@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(request: CompareRunRequest):
    """Handles streaming runs for comparing multiple constitution sets."""
    metadata_thread_id = request.thread_id
    run_id_in_db: Optional[int] = None # Not used directly here, but runs are added inside stream_events

    try:
        # 1. Validate input
        if not request.input or not request.input.content:
             raise HTTPException(status_code=400, detail="Input content is required for comparison.")
        if not request.constitution_sets and not inner_agent_app: # Need at least one set OR the inner agent
             raise HTTPException(status_code=400, detail="At least one constitution set (or inner agent) is required for comparison.")

        # 2. Ensure we have a metadata thread ID
        if metadata_thread_id is None:
            # Determine default name based on *first* set for simplicity
            first_const_ids = request.constitution_sets[0].constitution_ids if request.constitution_sets else ['none']
            default_name = _generate_default_thread_name(first_const_ids) + " [Comparison]"
            metadata_thread_id = await metadata_manager.add_thread(name=default_name)
            print(f"Implicitly created new Thread {metadata_thread_id} for comparison: '{default_name}'")
        else:
             thread_info = await metadata_manager.get_thread(metadata_thread_id)
             if not thread_info:
                  raise HTTPException(status_code=404, detail=f"Thread with ID {metadata_thread_id} not found.")

        # 3. Prepare runs to perform
        runs_to_perform: List[Tuple[str, List[str], str, Any]] = []
        compare_group_id = str(uuid.uuid4())

        # Superego-involved runs
        for i, const_set in enumerate(request.constitution_sets):
            set_name = const_set.id or f"set_{i+1}"
            checkpoint_thread_id = f"compare_{compare_group_id}_{set_name}"
            runs_to_perform.append(
                (checkpoint_thread_id, const_set.constitution_ids, set_name, graph_app)
            )
            # Note: The run entry in DB is now added inside stream_events,
            # triggered by stream_compare_events calling stream_events.
            # We pass compare_group_id via set_id to stream_events.

        # Inner Agent Only run
        if inner_agent_app:
            inner_set_id = "inner_agent_only"
            inner_checkpoint_thread_id = f"compare_{compare_group_id}_{inner_set_id}"
            runs_to_perform.append(
                (inner_checkpoint_thread_id, [], inner_set_id, inner_agent_app)
            )
        else:
             print("Warning: Inner agent app not available, skipping inner_agent_only comparison run.")

        # 4. Prepare input message
        input_message = HumanMessage(content=request.input.content)

        # 5. Return the SSE response stream
        return EventSourceResponse(stream_compare_events(
            metadata_thread_id=metadata_thread_id,
            input_message=input_message,
            runs_to_perform=runs_to_perform
        ))

    except HTTPException:
        raise
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
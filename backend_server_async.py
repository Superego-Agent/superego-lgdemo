# Standard library imports
import os
import uuid
import json
import asyncio
import traceback # Keep for explicit error logging
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Literal, Union, AsyncGenerator, Tuple

# Third-party imports
import aiosqlite
from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# Langchain/Langgraph specific imports
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import CheckpointTuple # Keep specific import

# Project-specific imports
try:
    from config import CONFIG # Assumed to exist and be configured
    from constitution_utils import get_available_constitutions, get_combined_constitution_content # Assumed to exist
    from superego_core_async import create_models, create_workflow # Assumed to exist
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Ensure backend_server_async.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH.")
    import sys
    sys.exit(1)

# --- Globals ---
graph_app: Any = None
checkpointer: Optional[AsyncSqliteSaver] = None # Type hint as Optional
inner_agent_app: Any = None

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown logic."""
    global graph_app, checkpointer, inner_agent_app
    print("Backend server starting up...")
    try:
        superego_model, inner_model = create_models()
        # Pass checkpointer creation details if needed by create_workflow,
        # or handle checkpointer creation/setup explicitly here if separate.
        graph_app, checkpointer, inner_agent_app = await create_workflow(
            superego_model=superego_model,
            inner_model=inner_model
        )
        # Ensure checkpointer (if created by create_workflow) has its setup called if necessary
        if checkpointer and hasattr(checkpointer, 'setup') and callable(checkpointer.setup):
             print("Running checkpointer setup...")
             await checkpointer.setup() # Explicitly call setup if needed
        elif not checkpointer:
             print("Warning: Checkpointer was not initialized during startup.")

        print("Models and graph loaded successfully.")
    except Exception as e:
        print(f"FATAL: Error during startup model/graph creation: {e}")
        traceback.print_exc() # Print full traceback for startup errors
        # Consider if the app should fully stop or try to continue degraded
        raise RuntimeError("Failed to initialize LangGraph workflow") from e

    yield # Application runs here

    # --- Shutdown ---
    print("Backend server shutting down...")
    if checkpointer and hasattr(checkpointer, 'conn') and checkpointer.conn:
        try:
            print("Closing database connection...")
            await checkpointer.conn.close()
            print("Database connection closed.")
        except Exception as e:
            print(f"Warning: Error closing checkpointer connection: {e}")

# --- FastAPI App ---
app = FastAPI(title="Superego Backend", lifespan=lifespan)

# --- CORS ---
# Allow all origins for development ease. Restrict in production.
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

class ThreadItem(BaseModel):
    thread_id: str
    title: str # Consider making title optional or generating dynamically

class HistoryMessage(BaseModel):
    # Matches structure in global.d.ts MessageType (roughly)
    id: str
    sender: Literal['human', 'ai', 'tool_result', 'system']
    content: Any # Allow flexibility, will be serialized
    timestamp: Optional[int] = None
    node: Optional[str] = None
    set_id: Optional[str] = None
    # Add fields if needed based on frontend display requirements
    # (e.g., structured tool calls, is_error for system messages)
    tool_name: Optional[str] = None # For tool_result sender
    is_error: Optional[bool] = None # For tool_result or system sender

class HistoryResponse(BaseModel):
    messages: List[HistoryMessage]

class NewThreadResponse(BaseModel):
    thread_id: str

class StreamRunInput(BaseModel):
    type: Literal["human"] # Only support human input for now
    content: str

class StreamRunRequest(BaseModel):
    thread_id: Optional[str] = None
    input: Optional[StreamRunInput] = None # Allow runs without initial input (e.g., just getting history?)
    constitution_ids: List[str] = ["none"]

class CompareRunSet(BaseModel):
    id: str # User-defined ID for the set (e.g., 'strict_vs_default')
    constitution_ids: List[str]

class CompareRunRequest(BaseModel):
    input: StreamRunInput # Compare runs always need an input
    constitution_sets: List[CompareRunSet]

# SSE Event Data Models (matching global.d.ts SSEEventData)
class SSEToolCallChunkData(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    args: Optional[str] = None # Args are streamed as string fragments

class SSEToolResultData(BaseModel):
    tool_name: str
    result: str # Result should always be stringified
    is_error: bool
    tool_call_id: Optional[str] = None # Corresponds to the AIMessage tool_call ID

class SSEEndData(BaseModel):
    thread_id: str

class SSEEventData(BaseModel):
    type: Literal["chunk", "ai_tool_chunk", "tool_result", "error", "end"]
    node: Optional[str] = None
    data: Union[str, SSEToolCallChunkData, SSEToolResultData, SSEEndData]
    set_id: Optional[str] = None # For compare mode tracking

# --- Helper Function for Standard Streaming ---
async def stream_events(
    thread_id: str,
    input_messages: Optional[List[BaseMessage]],
    constitution_ids: List[str],
    run_app: Any, # The compiled LangGraph app to run
    set_id: Optional[str] = None # Identifier for compare mode sets
) -> AsyncGenerator[ServerSentEvent, None]:
    """Generates Server-Sent Events for a single LangGraph run."""
    if not run_app:
        yield ServerSentEvent(data=SSEEventData(type="error", node="setup", data="Graph app not initialized.", set_id=set_id).model_dump_json())
        return
    if not checkpointer:
         yield ServerSentEvent(data=SSEEventData(type="error", node="setup", data="Checkpointer not initialized.", set_id=set_id).model_dump_json())
         return

    current_node_name: Optional[str] = None
    # Track last yielded text chunk per node/set_id to prevent duplicates if stream yields identical consecutive chunks
    last_yielded_text: Dict[Tuple[Optional[str], Optional[str]], str] = {}

    try:
        # Load constitution content
        constitution_content_for_run, loaded_ids = get_combined_constitution_content(constitution_ids)
        requested_set = set(id for id in constitution_ids if id != "none")
        missing_in_run = requested_set - set(loaded_ids)
        if missing_in_run:
            # Send a warning event if constitutions couldn't be loaded
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="setup", # Use 'error' type for warnings too? Or add 'warning' type?
                data=f"Warning: Constitution(s) not found/loaded: {', '.join(missing_in_run)}. Running without.",
                set_id=set_id
            ).model_dump_json())

        # Prepare run config
        config = {"configurable": {"thread_id": thread_id, "constitution_content": constitution_content_for_run}}
        stream_input = {'messages': input_messages} if input_messages else {}

        # Stream events from the LangGraph app
        stream = run_app.astream_events(stream_input, config=config, version="v1") # Use v1 events

        async for event in stream:
            event_type = event.get("event")
            event_name = event.get("name") # Often the node name for start/end events
            tags = event.get("tags", [])
            event_data = event.get("data", {})

            # --- Track Current Node ---
            # Heuristic: Assume the event name or a specific tag indicates the active node
            potential_node_tags = [tag for tag in tags if tag in ["superego", "inner_agent", "tools"]]
            if event_name in ["superego", "inner_agent", "tools"]:
                 current_node_name = event_name
            elif potential_node_tags:
                 current_node_name = potential_node_tags[-1] # Use the last relevant tag found

            yield_key = (current_node_name, set_id) # Key for deduplicating text chunks

            # --- Process Different Event Types ---

            # Text Chunk Events
            if event_type == "on_chat_model_stream" and isinstance(event_data.get("chunk"), AIMessageChunk):
                chunk: AIMessageChunk = event_data["chunk"]
                text_content = ""
                # Extract text content (handle string or list of dicts format)
                if isinstance(chunk.content, str):
                    text_content = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict):
                            # Handle different potential structures for text content within the list
                            if item.get("type") == "text":
                                text_content += item.get("text", "")
                            # Example: Handle Anthropic's content_block_delta
                            elif item.get("type") == "content_block_delta" and item.get("delta", {}).get("type") == "text_delta":
                                 text_content += item.get("delta", {}).get("text", "")

                # Yield text chunk if it's new content for this node/set
                if text_content:
                    last_text = last_yielded_text.get(yield_key, "")
                    # Simple dedupe: only yield if different from the absolute last chunk yielded for this node/set
                    if text_content != last_text:
                        sse_payload_text = SSEEventData(type="chunk", node=current_node_name, data=text_content, set_id=set_id)
                        yield ServerSentEvent(data=sse_payload_text.model_dump_json())
                        last_yielded_text[yield_key] = text_content # Update last yielded text

                # Tool Call Chunk Events
                tool_chunks = getattr(chunk, 'tool_call_chunks', [])
                if tool_chunks:
                    for tc_chunk in tool_chunks:
                        # Ensure required fields for SSEToolCallChunkData are present
                        chunk_data = SSEToolCallChunkData(
                            id=tc_chunk.get("id"), # Pass the tool call ID
                            name=tc_chunk.get("name"),
                            args=tc_chunk.get("args") # Args are fragments
                        )
                        sse_payload_tool = SSEEventData(type="ai_tool_chunk", node=current_node_name, data=chunk_data, set_id=set_id)
                        yield ServerSentEvent(data=sse_payload_tool.model_dump_json())

            # Tool Result Events
            elif event_type == "on_tool_end":
                 tool_output = event_data.get("output")
                 # Stringify tool output robustly
                 try:
                      output_str = json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output
                 except Exception:
                      output_str = str(tool_output)

                 tool_func_name = event.get("name") # Name of the tool function that ran
                 is_error = isinstance(tool_output, Exception) # Check if the output itself is an Exception

                 # Extract tool_call_id if available (may depend on LangGraph version/event structure)
                 # Heuristic: Look for parent run IDs, might contain the triggering tool call ID
                 tool_call_id = None
                 parent_ids = event_data.get("parent_run_ids") # Check standard key
                 if isinstance(parent_ids, list):
                     # Often the direct parent is the tool call invocation ID
                     # Look for standard LangChain UUID format if needed, or just take the last one?
                      possible_ids = [pid for pid in parent_ids if isinstance(pid, str)] # Simple check for string IDs
                      if possible_ids:
                         tool_call_id = possible_ids[-1] # Assume last parent is most relevant

                 sse_payload_data = SSEToolResultData(
                     tool_name=tool_func_name or "unknown_tool",
                     result=output_str,
                     is_error=is_error,
                     tool_call_id=tool_call_id
                 )
                 sse_payload = SSEEventData(type="tool_result", node="tools", data=sse_payload_data, set_id=set_id) # Assume node is 'tools'
                 yield ServerSentEvent(data=sse_payload.model_dump_json())

        # Signal end of stream for this run
        yield ServerSentEvent(data=SSEEventData(type="end", node=current_node_name or "graph", data=SSEEndData(thread_id=thread_id), set_id=set_id).model_dump_json())

    except Exception as e:
        print(f"Stream Error (Thread: {thread_id}, Set: {set_id}): {e}")
        traceback.print_exc()
        # Send an error event to the client
        try:
            error_data = f"Streaming error: {str(e)}"
            yield ServerSentEvent(data=SSEEventData(type="error", node=current_node_name or "graph", data=error_data, set_id=set_id).model_dump_json())
        except Exception as inner_e:
            print(f"Failed to send stream error event: {inner_e}")


# --- API Endpoints ---

@app.get("/api/constitutions", response_model=List[ConstitutionItem])
async def get_constitutions_endpoint():
    """Returns a list of available constitutions."""
    try:
        constitutions_dict = get_available_constitutions()
        # Ensure 'none' constitution exists with basic info
        if "none" not in constitutions_dict:
            constitutions_dict["none"] = {"name": "None", "description": "No constitution applied."}
        elif not isinstance(constitutions_dict.get("none"), dict):
             constitutions_dict["none"] = {"name": "None", "description": str(constitutions_dict.get("none", "N/A"))}

        # Convert dict to list of ConstitutionItem, handling potential non-dict values gracefully
        response_items = []
        for k, v in constitutions_dict.items():
             if isinstance(v, dict):
                  response_items.append(ConstitutionItem(
                       id=k,
                       name=v.get('name', k.replace('_', ' ').title()), # Default name from ID
                       description=v.get('description')
                  ))
             else:
                  print(f"Warning: Constitution '{k}' has non-dictionary value: {v}. Skipping.")

        return response_items
    except Exception as e:
        print(f"Error loading constitutions: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load constitutions: {str(e)}")


@app.get("/api/threads", response_model=List[ThreadItem])
async def get_threads_endpoint():
    """Lists recent chat threads based on checkpointer entries."""
    if not checkpointer or not hasattr(checkpointer, 'conn'):
        # Handle case where checkpointer didn't initialize properly
        print("Error: Checkpointer not available for listing threads.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    thread_items = []
    try:
        # Use checkpointer's list method if it supports filtering/listing thread_ids
        # The base interface requires a 'config' which might not be useful here.
        # We might need a more direct query if `list` isn't suitable.

        # Alternative: Direct DB query (assuming AsyncSqliteSaver)
        query = "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT 100;" # Get recent thread IDs
        conn = checkpointer.conn # Access underlying connection
        cursor = await conn.execute(query)
        distinct_thread_ids = [row[0] for row in await cursor.fetchall() if row and row[0]]
        await cursor.close()

        # Create ThreadItem objects (consider fetching titles/timestamps later if needed)
        for thread_id in distinct_thread_ids:
            # Filter out compare threads if desired?
            # if "_compare_" not in thread_id:
            thread_items.append(ThreadItem(thread_id=thread_id, title=f"Chat {thread_id[:8]}")) # Simple title

        return thread_items
    except aiosqlite.OperationalError as db_err:
        print(f"Database error listing threads: {db_err}")
        traceback.print_exc()
        # Check if table doesn't exist, return empty list gracefully
        if "no such table" in str(db_err).lower():
            print("Checkpoints table not found. Returning empty thread list.")
            return []
        raise HTTPException(status_code=500, detail=f"Database error accessing threads: {db_err}")
    except Exception as e:
        print(f"Error listing threads: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to list threads due to an unexpected error.")


# Corrected history endpoint
@app.get("/api/threads/{thread_id}/history", response_model=HistoryResponse)
async def get_thread_history_endpoint(thread_id: str = FastApiPath(...)):
    """Retrieves the message history for a given thread ID."""
    if not checkpointer:
        print("Error: Checkpointer not available for getting history.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    # Define config for checkpointer call *before* using it
    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Validate the thread_id format
        try:
            uuid.UUID(thread_id, version=4)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid thread ID format.")

        # Use the asynchronous method aget_tuple()
        checkpoint_tuple: Optional[CheckpointTuple] = await checkpointer.aget_tuple(config)

        history_messages: List[HistoryMessage] = []
        if checkpoint_tuple and checkpoint_tuple.checkpoint:
            messages_from_state = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            ts_value = checkpoint_tuple.checkpoint.get("ts")
            base_timestamp_ms = None
            # Robust timestamp handling
            if ts_value and hasattr(ts_value, 'timestamp') and callable(ts_value.timestamp):
                 try:
                    # Attempt to convert to UNIX milliseconds
                    base_timestamp_ms = int(ts_value.timestamp() * 1000)
                 except (TypeError, ValueError) as ts_err:
                     print(f"Warning: Could not convert timestamp '{ts_value}' ({type(ts_value)}) to UNIX ms for thread {thread_id}: {ts_err}")

            for i, msg in enumerate(messages_from_state):
                sender: Literal['human', 'ai', 'tool_result', 'system'] = "system" # Default
                node = getattr(msg, 'name', None) # Get node if available (e.g., from AIMessage)
                content = msg.content
                tool_name: Optional[str] = None
                is_error: Optional[bool] = None

                # Determine sender and potentially extract/format content
                if isinstance(msg, AIMessage):
                     sender = "ai"
                     # Format content and tool calls for display
                     if tool_calls := getattr(msg, "tool_calls", None):
                         # Simple text representation for history 'content' field:
                         calls_str = "\n".join([
                             f"-> Called Tool: {tc.get('name', 'N/A')}({json.dumps(tc.get('args', {}))})"
                             for tc in tool_calls if isinstance(tc, dict)
                         ])
                         # Append tool call info to content string
                         if isinstance(content, str): content += f"\n{calls_str}"
                         else: content = str(content) + f"\n{calls_str}"
                elif isinstance(msg, HumanMessage):
                     sender = "human"
                elif isinstance(msg, ToolMessage):
                     sender = "tool_result"
                     node = "tools" # Associate with the tools node
                     tool_name = getattr(msg, 'name', 'unknown_tool')
                     is_error = isinstance(msg.content, Exception) # Check if tool produced an error
                     # Ensure content is stringified for JSON response
                     if not isinstance(content, str):
                         try: content = json.dumps(content)
                         except TypeError: content = str(content)

                # Calculate timestamp if possible
                msg_timestamp = base_timestamp_ms + i if base_timestamp_ms is not None else None

                history_messages.append(HistoryMessage(
                    id=f"{thread_id}-{i}", # Simple unique ID for frontend keying
                    sender=sender,
                    content=content, # Content is now stringified/formatted
                    timestamp=msg_timestamp,
                    node=node,
                    tool_name=tool_name,
                    is_error=is_error,
                    # set_id is not applicable for single thread history
                ))

        return HistoryResponse(messages=history_messages)

    except HTTPException: # Re-raise validation or explicit HTTP errors
        raise
    except Exception as e:
        print(f"Error getting history for thread {thread_id}: {e}")
        traceback.print_exc() # Log full traceback for server debugging
        raise HTTPException(status_code=500, detail="Failed to load history due to an unexpected server error.")


@app.post("/api/threads", response_model=NewThreadResponse)
async def create_thread_endpoint():
    """Creates a new thread ID."""
    # Note: This doesn't interact with the checkpointer directly, just generates an ID.
    # The checkpointer entry is created on the first run within that thread.
    new_thread_id = str(uuid.uuid4())
    print(f"Created new thread ID: {new_thread_id}")
    return NewThreadResponse(thread_id=new_thread_id)


@app.post("/api/runs/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    """Handles streaming runs for a single thread (normal chat)."""
    thread_id = request.thread_id
    input_messages = None

    if not thread_id:
        # If no thread ID is provided, create a new one for this run
        thread_id = str(uuid.uuid4())
        print(f"Starting new stream in implicitly created thread: {thread_id}")
    else:
        # Validate existing thread_id format if provided
        try:
            uuid.UUID(thread_id, version=4)
            print(f"Continuing stream in thread: {thread_id}")
        except ValueError:
             print(f"Invalid thread_id format received: {thread_id}")
             # Return an error response instead of streaming
             # (Requires adjustments to return type or exception handling)
             # For now, let stream_events handle potential checkpointer errors
             pass # Or raise HTTPException(status_code=400, detail="Invalid thread ID format.")


    if request.input:
        input_messages = [HumanMessage(content=request.input.content)]
    else:
        # Handle runs without initial input if necessary (e.g., resuming a state)
        # Currently, stream_events expects input messages if provided
        print(f"Warning: Stream run requested for thread {thread_id} without initial input.")
        # input_messages = [] # Or handle based on graph requirements

    # Return the SSE response stream
    return EventSourceResponse(stream_events(
        thread_id=thread_id,
        input_messages=input_messages,
        constitution_ids=request.constitution_ids,
        run_app=graph_app # Use the main graph app
    ))


# --- Compare Streaming Helper and Endpoint ---

async def consume_and_forward_stream(
    stream: AsyncGenerator[ServerSentEvent, None],
    queue: asyncio.Queue
):
    """Consumes events from a stream and puts them onto a shared queue."""
    try:
        async for event in stream:
            await queue.put(event)
    except Exception as e:
        print(f"Error consuming stream: {e}")
        # Put an error event onto the queue to signal failure
        error_event = ServerSentEvent(data=SSEEventData(type="error", node="compare_consumer", data=f"Stream consumption error: {e}").model_dump_json())
        await queue.put(error_event)
    finally:
        # Signal completion (or error) for this specific stream consumer
        await queue.put(None)


async def stream_compare_events(
    input_message: BaseMessage,
    constitution_sets: List[CompareRunSet]
) -> AsyncGenerator[ServerSentEvent, None]:
    """Runs multiple streams concurrently for comparison and multiplexes their events."""
    compare_run_uuid = str(uuid.uuid4())[:8] # Short ID for this comparison run
    event_queue = asyncio.Queue()
    consumer_tasks = []
    active_stream_count = 0

    # --- Launch Superego-involved runs ---
    for i, const_set in enumerate(constitution_sets):
        set_name = const_set.id
        # Use a temporary, unique thread ID for each compare run to avoid state collision
        temp_thread_id = f"compare_{compare_run_uuid}_{set_name}"
        print(f"Compare: Launching Set='{set_name}', Temp Thread='{temp_thread_id}'")
        stream = stream_events(
            thread_id=temp_thread_id,
            input_messages=[input_message],
            constitution_ids=const_set.constitution_ids,
            run_app=graph_app, # Use main graph
            set_id=set_name # Pass set_id for frontend tracking
        )
        task = asyncio.create_task(consume_and_forward_stream(stream, event_queue))
        consumer_tasks.append(task)
        active_stream_count += 1

    # --- Launch Inner Agent Only run ---
    if inner_agent_app:
        inner_set_id = "inner_agent_only" # Special ID for this run
        inner_temp_thread_id = f"compare_{compare_run_uuid}_{inner_set_id}"
        print(f"Compare: Launching Set='{inner_set_id}', Temp Thread='{inner_temp_thread_id}'")
        inner_stream = stream_events(
            thread_id=inner_temp_thread_id,
            input_messages=[input_message],
            constitution_ids=[], # No constitution for inner agent
            run_app=inner_agent_app, # Use the inner-agent-only graph
            set_id=inner_set_id
        )
        inner_task = asyncio.create_task(consume_and_forward_stream(inner_stream, event_queue))
        consumer_tasks.append(inner_task)
        active_stream_count += 1
    else:
         print("Warning: Inner agent app not available, skipping inner_agent_only comparison run.")


    # --- Multiplex events from the queue ---
    finished_streams = 0
    while finished_streams < active_stream_count:
        try:
            # Wait for an event from any stream consumer
            event = await event_queue.get()
            if event is None:
                # A stream finished (or errored out)
                finished_streams += 1
                continue

            # Yield the event to the client
            yield event
            event_queue.task_done() # Mark task as done for queue management

        except asyncio.CancelledError:
             print("Compare event streaming cancelled.")
             break
        except Exception as e:
            print(f"Error processing compare event queue: {e}")
            # Yield a high-level error to the client
            yield ServerSentEvent(data=SSEEventData(
                type="error",
                node="compare_multiplexer",
                data=f"Compare error: {e}"
            ).model_dump_json())

    print("Compare streaming finished.")
    # Ensure all consumer tasks are awaited/cancelled properly (optional cleanup)
    for task in consumer_tasks:
         if not task.done():
             task.cancel()
    await asyncio.gather(*consumer_tasks, return_exceptions=True)


@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(request: CompareRunRequest):
    """Handles streaming runs for comparing multiple constitution sets."""
    # Validate input
    if not request.input or not request.input.content:
         raise HTTPException(status_code=400, detail="Input content is required for comparison.")
    if not request.constitution_sets:
         raise HTTPException(status_code=400, detail="At least one constitution set is required for comparison.")

    input_message = HumanMessage(content=request.input.content)
    return EventSourceResponse(stream_compare_events(
        input_message=input_message,
        constitution_sets=request.constitution_sets
    ))

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    # Check for essential environment variables
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY environment variable not set. LangGraph models may fail.")

    # Server configuration
    host = os.getenv("BACKEND_HOST", "0.0.0.0") # Changed HOST to BACKEND_HOST
    port = int(os.getenv("BACKEND_PORT", "8000")) # Changed PORT to BACKEND_PORT
    reload = os.getenv("BACKEND_RELOAD", "true").lower() == "true" # Changed RELOAD

    print(f"Starting Uvicorn server on {host}:{port} (Reload: {'enabled' if reload else 'disabled'})")
    uvicorn.run(
        "backend_server_async:app", # Reference the FastAPI app instance
        host=host,
        port=port,
        reload=reload,
        log_level="info" # Adjust log level as needed
    )
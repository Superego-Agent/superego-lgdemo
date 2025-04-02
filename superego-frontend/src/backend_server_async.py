# src/backend_server_async.py

# Standard library imports
import os
import uuid
import json
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Literal, Union, AsyncGenerator, Tuple
from datetime import datetime

# Third-party imports
import aiosqlite
from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, Request, Depends # Added Depends
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# Langchain/Langgraph specific imports
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk
from langchain_core.runnables import RunnableConfig # For type hinting config
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import CheckpointTuple, BaseCheckpointSaver

# Project-specific imports
try:
    from config import CONFIG
    from constitution_utils import get_available_constitutions, get_combined_constitution_content
    from superego_core_async import create_models, create_workflow
    import metadata_manager
    from metadata_manager import _generate_default_thread_name
except ImportError as e:
    # ... (error handling) ...
    print(f"Error importing project modules: {e}")
    print("Ensure backend_server_async.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH.")
    import sys
    sys.exit(1)

# --- Globals ---
# Use a dictionary to hold globals that will be initialized in lifespan
app_globals: Dict[str, Any] = {
    "graph_app": None,
    "checkpointer": None,
    "inner_agent_app": None,
}

# --- Dependency Injection for Globals ---
# This allows FastAPI endpoints to easily access initialized components
async def get_graph_app() -> Any:
    if app_globals["graph_app"] is None:
        raise HTTPException(status_code=503, detail="Graph App not initialized")
    return app_globals["graph_app"]

async def get_checkpointer() -> BaseCheckpointSaver:
    if app_globals["checkpointer"] is None:
        raise HTTPException(status_code=503, detail="Checkpointer not initialized")
    return app_globals["checkpointer"]

async def get_inner_agent_app() -> Any:
    if app_globals["inner_agent_app"] is None:
        # Maybe optional? Or raise error if required?
        print("Warning: Inner agent app accessed before initialization.")
        # raise HTTPException(status_code=503, detail="Inner Agent App not initialized")
    return app_globals["inner_agent_app"]


# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown logic."""
    print("Backend server starting up...")
    try:
        await metadata_manager.init_db()

        superego_model, inner_model = create_models()
        graph_app_instance, checkpointer_instance, inner_agent_app_instance = await create_workflow(
            superego_model=superego_model,
            inner_model=inner_model
        )

        # Store instances in globals dictionary
        app_globals["graph_app"] = graph_app_instance
        app_globals["checkpointer"] = checkpointer_instance
        app_globals["inner_agent_app"] = inner_agent_app_instance


        if not checkpointer_instance: print("Warning: Checkpointer was not initialized during startup.")
        if not graph_app_instance: print("Warning: Main graph app was not initialized.")
        # Inner agent app might be optional depending on compare logic
        # if not inner_agent_app_instance: print("Warning: Inner agent app was not initialized.")

        print("Models, graph, and databases initialized successfully.")
    except Exception as e:
        print(f"FATAL: Error during startup: {e}")
        traceback.print_exc()
        # Reset globals on failure
        app_globals["graph_app"] = None
        app_globals["checkpointer"] = None
        app_globals["inner_agent_app"] = None
        raise RuntimeError("Failed to initialize backend components") from e

    yield # Application runs here

    print("Backend server shutting down...")
    checkpointer_to_close = app_globals.get("checkpointer")
    if checkpointer_to_close and isinstance(checkpointer_to_close, AsyncSqliteSaver) and checkpointer_to_close.conn:
         try:
              print("Attempting to close checkpointer DB connection...")
              await checkpointer_to_close.conn.close()
              print("Checkpointer DB connection closed.")
         except Exception as e:
              print(f"Warning: Error closing checkpointer connection: {e}")
    # Clear globals on shutdown
    app_globals["graph_app"] = None
    app_globals["checkpointer"] = None
    app_globals["inner_agent_app"] = None


# --- FastAPI App ---
app = FastAPI(title="Superego Backend", lifespan=lifespan)
# --- CORS ---
# ... (no changes) ...
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- Pydantic Models ---
# ... (no changes from previous version) ...
class ConstitutionItem(BaseModel): id: str; name: str; description: Optional[str] = None
class ThreadItem(BaseModel): thread_id: int; name: str; last_updated: Optional[datetime] = None
class RenameThreadRequest(BaseModel): new_name: str
class HistoryMessage(BaseModel): id: str; sender: Literal['human', 'ai', 'tool_result', 'system']; content: Any; timestamp: Optional[int] = None; node: Optional[str] = None; set_id: Optional[str] = None; tool_name: Optional[str] = None; is_error: Optional[bool] = None
class HistoryResponse(BaseModel): messages: List[HistoryMessage]; thread_id: int; thread_name: Optional[str] = None
class StreamRunInput(BaseModel): type: Literal["human"]; content: str
class StreamRunRequest(BaseModel): thread_id: Optional[int] = None; input: StreamRunInput; constitution_ids: List[str] = ["none"]
class CompareRunSet(BaseModel): id: str; constitution_ids: List[str]
class CompareRunRequest(BaseModel): thread_id: Optional[int] = None; input: StreamRunInput; constitution_sets: List[CompareRunSet]
class SSEToolCallChunkData(BaseModel): id: Optional[str] = None; name: Optional[str] = None; args: Optional[str] = None
class SSEToolResultData(BaseModel): tool_name: str; result: str; is_error: bool; tool_call_id: Optional[str] = None
class SSEEndData(BaseModel): thread_id: int
class SSEEventData(BaseModel): type: Literal["chunk", "ai_tool_chunk", "tool_result", "error", "end"]; node: Optional[str] = None; data: Union[str, SSEToolCallChunkData, SSEToolResultData, SSEEndData]; set_id: Optional[str] = None

# --- Helper Function for Standard Streaming ---
async def stream_events(
    metadata_thread_id: int,
    checkpoint_thread_id: str, # The unique ID for this specific run's checkpoints in conversations.db
    input_messages: List[BaseMessage], # Now potentially the FULL history + new message
    constitution_ids: List[str],
    run_app: Any, # The compiled LangGraph app to run
    checkpointer_instance: BaseCheckpointSaver, # Pass checkpointer for potential use inside (though not currently needed here)
    set_id: Optional[str] = None
) -> AsyncGenerator[ServerSentEvent, None]:
    """Generates Server-Sent Events for a single LangGraph run."""
    # Checkpointer instance is now passed, but check is implicit via Depends
    if not run_app:
        error_data = "Graph app not initialized."
        # ... (yield error and return) ...
        yield ServerSentEvent(data=SSEEventData(type="error", node="setup", data=error_data, set_id=set_id).model_dump_json())
        return

    current_node_name: Optional[str] = None
    last_yielded_text: Dict[Tuple[Optional[str], Optional[str]], str] = {}
    run_id_for_db: Optional[int] = None

    try:
        # Add run entry *before* starting stream
        # Using UNIQUE checkpoint_thread_id, so this is safe
        run_id_for_db = await metadata_manager.add_run(
            parent_thread_id=metadata_thread_id,
            checkpoint_thread_id=checkpoint_thread_id,
            constitution_ids=constitution_ids,
            compare_group_id=set_id # Use set_id as compare_group_id if present
        )
        print(f"DB Run {run_id_for_db}: Added for Checkpoint Thread {checkpoint_thread_id} (Parent: {metadata_thread_id})")

        # Load constitution content
        constitution_content_for_run, loaded_ids = get_combined_constitution_content(constitution_ids)
        # ... (warning for missing constitutions) ...
        requested_set = set(id for id in constitution_ids if id != "none")
        missing_in_run = requested_set - set(loaded_ids)
        if missing_in_run:
             yield ServerSentEvent(data=SSEEventData(
                 type="error", node="setup",
                 data=f"Warning: Constitution(s) not found/loaded: {', '.join(missing_in_run)}. Running without.",
                 set_id=set_id
             ).model_dump_json())

        # Prepare run config using the UNIQUE checkpoint_thread_id
        config: RunnableConfig = {"configurable": {"thread_id": checkpoint_thread_id, "constitution_content": constitution_content_for_run}}

        # Prepare input: Use the FULL message list provided
        # This list now contains history + new user message
        stream_input = {'messages': input_messages}
        print(f"Streaming with Checkpoint Thread ID: {checkpoint_thread_id}, Input messages count: {len(input_messages)}")

        # Stream events from the LangGraph app
        # Checkpointer is automatically used by the compiled app via config
        stream = run_app.astream_events(stream_input, config=config, version="v1")

        final_state_checkpoint_id: Optional[str] = None # Variable to capture final checkpoint id

        async for event in stream:
            event_type = event.get("event")
            # Extract checkpoint ID if it's the final 'on_graph_end' event
            # Note: The exact structure/event name for the final checkpoint might vary slightly
            if event_type == "on_graph_end" or event_type == "on_chain_end": # Check common end events
                event_metadata = event.get("metadata", {})
                # Look for checkpoint ID within standard config or metadata keys
                final_state_checkpoint_id = event_metadata.get("checkpoint_id") or \
                                           event_metadata.get("configurable", {}).get("checkpoint_id")

            # --- Process stream events (text chunks, tool calls/results) ---
            # (This logic remains the same as the previous working version)
            # ... (event processing logic: track node, handle text chunk, tool chunk, tool result) ...
            event_name = event.get("name")
            tags = event.get("tags", [])
            event_data = event.get("data", {})
            potential_node_tags = [tag for tag in tags if tag in ["superego", "inner_agent", "tools"]]
            if event_name in ["superego", "inner_agent", "tools"]: current_node_name = event_name
            elif potential_node_tags: current_node_name = potential_node_tags[-1]
            yield_key = (current_node_name, set_id)
            if event_type == "on_chat_model_stream" and isinstance(event_data.get("chunk"), AIMessageChunk):
                chunk: AIMessageChunk = event_data["chunk"]
                text_content = ""
                if isinstance(chunk.content, str): text_content = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict):
                            if item.get("type") == "text": text_content += item.get("text", "")
                            elif item.get("type") == "content_block_delta" and item.get("delta", {}).get("type") == "text_delta": text_content += item.get("delta", {}).get("text", "")
                if text_content:
                    last_text = last_yielded_text.get(yield_key, "")
                    if text_content != last_text:
                        sse_payload_text = SSEEventData(type="chunk", node=current_node_name, data=text_content, set_id=set_id)
                        yield ServerSentEvent(data=sse_payload_text.model_dump_json())
                        last_yielded_text[yield_key] = text_content
                tool_chunks = getattr(chunk, 'tool_call_chunks', []) # Check for tool chunks here
                if tool_chunks:
                    for tc_chunk in tool_chunks:
                        chunk_data = SSEToolCallChunkData(id=tc_chunk.get("id"), name=tc_chunk.get("name"), args=tc_chunk.get("args"))
                        sse_payload_tool = SSEEventData(type="ai_tool_chunk", node=current_node_name, data=chunk_data, set_id=set_id)
                        yield ServerSentEvent(data=sse_payload_tool.model_dump_json())
            elif event_type == "on_tool_end":
                 tool_output = event_data.get("output")
                 try: output_str = json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output
                 except Exception: output_str = str(tool_output)
                 tool_func_name = event.get("name"); is_error = isinstance(tool_output, Exception)
                 tool_call_id = None; parent_ids = event_data.get("parent_run_ids")
                 if isinstance(parent_ids, list):
                      possible_ids = [pid for pid in parent_ids if isinstance(pid, str)]
                      if possible_ids: tool_call_id = possible_ids[-1]
                 sse_payload_data = SSEToolResultData(tool_name=tool_func_name or "unknown_tool", result=output_str, is_error=is_error, tool_call_id=tool_call_id)
                 sse_payload = SSEEventData(type="tool_result", node="tools", data=sse_payload_data, set_id=set_id)
                 yield ServerSentEvent(data=sse_payload.model_dump_json())
            # --- End event processing ---


        # --- Stream End ---
        yield ServerSentEvent(data=SSEEventData(type="end", node=current_node_name or "graph", data=SSEEndData(thread_id=metadata_thread_id), set_id=set_id).model_dump_json())

        # --- Post-Stream: Update final checkpoint ID ---
        final_cp_id_to_update = final_state_checkpoint_id # Captured from stream events
        if not final_cp_id_to_update:
            # Fallback: If not captured from stream, try getting latest tuple
            print(f"Warning: Final checkpoint ID not captured from stream events for {checkpoint_thread_id}. Attempting fallback.")
            try:
                final_checkpoint_tuple = await checkpointer_instance.aget_tuple(config)
                if final_checkpoint_tuple and final_checkpoint_tuple.checkpoint:
                    # Structure might vary, adjust keys as needed ('ts', 'id', etc.)
                    final_cp_id_to_update = final_checkpoint_tuple.checkpoint.get("id") or str(final_checkpoint_tuple.checkpoint.get("ts"))
            except Exception as cp_err:
                 print(f"Warning: Failed fallback checkpointer.aget_tuple for run {run_id_for_db}: {cp_err}")

        if final_cp_id_to_update and run_id_for_db:
            try:
                await metadata_manager.update_run_final_checkpoint(run_id_for_db, final_cp_id_to_update)
                print(f"DB Run {run_id_for_db}: Updated final checkpoint ID to {final_cp_id_to_update}")
            except Exception as db_err:
                 print(f"Error updating final checkpoint ID in DB for run {run_id_for_db}: {db_err}")
        elif run_id_for_db:
             print(f"Warning: Could not determine final checkpoint ID for run {run_id_for_db}. DB not updated.")


    except Exception as e:
        # ... (error handling, ensure end event is sent) ...
        print(f"Stream Error (Metadata Thread: {metadata_thread_id}, Checkpoint Thread: {checkpoint_thread_id}, Set: {set_id}): {e}")
        traceback.print_exc()
        try:
            error_data = f"Streaming error: {str(e)}"
            yield ServerSentEvent(data=SSEEventData(type="error", node=current_node_name or "graph", data=error_data, set_id=set_id).model_dump_json())
            yield ServerSentEvent(data=SSEEventData(type="end", node="error", data=SSEEndData(thread_id=metadata_thread_id), set_id=set_id).model_dump_json())
        except Exception as inner_e:
            print(f"Failed to send stream error event: {inner_e}")


# --- API Endpoints ---

@app.get("/api/constitutions", response_model=List[ConstitutionItem])
async def get_constitutions_endpoint():
    # ... (no changes) ...
    try:
        constitutions_dict = get_available_constitutions()
        if "none" not in constitutions_dict: constitutions_dict["none"] = {"name": "None", "description": "No constitution applied."}
        elif not isinstance(constitutions_dict.get("none"), dict): constitutions_dict["none"] = {"name": "None", "description": str(constitutions_dict.get("none", "N/A"))}
        response_items = []
        for k, v in constitutions_dict.items():
              if isinstance(v, dict): response_items.append(ConstitutionItem(id=k, name=v.get('name', k.replace('_', ' ').title()), description=v.get('description')))
              else: print(f"Warning: Constitution '{k}' has non-dictionary value: {v}. Skipping.")
        return response_items
    except Exception as e: print(f"Error loading constitutions: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Failed to load constitutions: {str(e)}")

@app.get("/api/threads", response_model=List[ThreadItem])
async def get_threads_endpoint():
    # ... (no changes - already uses metadata manager) ...
    try:
        threads_data = await metadata_manager.list_threads()
        return [ThreadItem(thread_id=t['thread_id'], name=t['name'], last_updated=t['last_updated']) for t in threads_data]
    except Exception as e: print(f"Error listing threads from metadata DB: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to list threads.")

@app.put("/api/threads/{thread_id}/rename")
async def rename_thread_endpoint(
    thread_id: int = FastApiPath(..., title="The metadata ID of the thread to rename"),
    request: RenameThreadRequest = Body(...)
):
    # ... (no changes - already uses metadata manager) ...
     if not request.new_name or len(request.new_name.strip()) == 0: raise HTTPException(status_code=400, detail="New name cannot be empty.")
     try:
         thread_info = await metadata_manager.get_thread(thread_id)
         if not thread_info: raise HTTPException(status_code=404, detail=f"Thread with ID {thread_id} not found.")
         await metadata_manager.rename_thread(thread_id, request.new_name.strip())
         print(f"Thread {thread_id} renamed to '{request.new_name.strip()}'")
         updated_thread = await metadata_manager.get_thread(thread_id)
         if updated_thread: return ThreadItem(thread_id=updated_thread['thread_id'], name=updated_thread['name'], last_updated=updated_thread['last_updated'])
         else: raise HTTPException(status_code=500, detail="Failed to retrieve thread info after rename.")
     except HTTPException: raise
     except Exception as e: print(f"Error renaming thread {thread_id}: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Failed to rename thread.")

@app.get("/api/threads/{thread_id}/history", response_model=HistoryResponse)
async def get_thread_history_endpoint(
    thread_id: int = FastApiPath(..., title="The metadata ID of the thread"),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer) # Inject checkpointer
):
    """
    Retrieves the message history for the LATEST run of a given thread.
    Relies on the latest run's checkpoint containing the full accumulated state.
    """
    # Checkpointer is now injected via Depends(get_checkpointer)
    try:
        thread_info = await metadata_manager.get_thread(thread_id)
        if not thread_info: raise HTTPException(status_code=404, detail=f"Thread with ID {thread_id} not found.")
        thread_name = thread_info.get('name')

        latest_checkpoint_thread_id = await metadata_manager.get_latest_checkpoint_thread_id(thread_id)

        if not latest_checkpoint_thread_id:
            print(f"No runs found for thread {thread_id}. Returning empty history.")
            return HistoryResponse(messages=[], thread_id=thread_id, thread_name=thread_name)

        print(f"Fetching history for Thread {thread_id} using latest Checkpoint Thread ID: {latest_checkpoint_thread_id}")

        config = {"configurable": {"thread_id": latest_checkpoint_thread_id}}
        checkpoint_tuple: Optional[CheckpointTuple] = await checkpointer.aget_tuple(config)

        history_messages: List[HistoryMessage] = []
        if checkpoint_tuple and checkpoint_tuple.checkpoint:
             messages_from_state = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
             # ... (message processing logic - unchanged from previous version) ...
             ts_value = checkpoint_tuple.checkpoint.get("ts"); base_timestamp_ms = None
             if ts_value and hasattr(ts_value, 'timestamp') and callable(ts_value.timestamp):
                  try: base_timestamp_ms = int(ts_value.timestamp() * 1000)
                  except (TypeError, ValueError) as ts_err: print(f"Warning: Could not convert timestamp '{ts_value}' ({type(ts_value)}) to UNIX ms for thread {thread_id}: {ts_err}")
             for i, msg in enumerate(messages_from_state):
                 sender: Optional[Literal['human', 'ai', 'tool_result', 'system']] = None; node: Optional[str] = None; formatted_content: Optional[str] = None; tool_name: Optional[str] = None; is_error: Optional[bool] = None
                 if isinstance(msg, HumanMessage): sender = "human"; node = getattr(msg, 'name', None); formatted_content = str(msg.content) if msg.content is not None else ""
                 elif isinstance(msg, AIMessage):
                     sender = "ai"; node = getattr(msg, 'name', 'ai'); raw_content = msg.content; content_str = ""
                     if isinstance(raw_content, list):
                         for item in raw_content:
                             if isinstance(item, dict) and item.get("type") == "text": content_str += item.get("text", "")
                     elif isinstance(raw_content, str): content_str = raw_content
                     elif raw_content is not None: content_str = str(raw_content)
                     tool_calls_str = ""
                     if tool_calls := getattr(msg, "tool_calls", None): tool_calls_str = "\n".join([f"-> Called Tool: {tc.get('name', 'N/A')}({json.dumps(tc.get('args', {}))})" for tc in tool_calls if isinstance(tc, dict)])
                     if content_str and tool_calls_str: formatted_content = f"{content_str}\n{tool_calls_str}"
                     elif content_str: formatted_content = content_str
                     elif tool_calls_str: formatted_content = tool_calls_str
                     else: formatted_content = ""
                 elif isinstance(msg, ToolMessage):
                     sender = "tool_result"; node = "tools"; tool_name = getattr(msg, 'name', 'unknown_tool'); is_error = isinstance(msg.content, Exception)
                     if isinstance(msg.content, str): formatted_content = msg.content
                     elif msg.content is None: formatted_content = ""
                     else:
                         try: formatted_content = json.dumps(msg.content)
                         except TypeError: formatted_content = str(msg.content)
                 if sender and formatted_content is not None:
                     msg_timestamp = base_timestamp_ms + i if base_timestamp_ms is not None else None
                     history_messages.append(HistoryMessage(id=f"{latest_checkpoint_thread_id}-{i}", sender=sender, content=formatted_content, timestamp=msg_timestamp, node=node, tool_name=tool_name, is_error=is_error))

        # Now history_messages should contain the full conversation history
        return HistoryResponse(messages=history_messages, thread_id=thread_id, thread_name=thread_name)

    except HTTPException: raise
    except Exception as e: print(f"Error getting history for thread {thread_id}: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to load history.")

# --- Run Endpoints ---

@app.post("/api/runs/stream")
async def run_stream_endpoint(
    request: StreamRunRequest,
    graph_app: Any = Depends(get_graph_app), # Inject graph app
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer) # Inject checkpointer
):
    """Handles streaming runs, ensuring state continuity."""
    metadata_thread_id = request.thread_id
    current_input_message = HumanMessage(content=request.input.content)
    previous_messages: List[BaseMessage] = []

    try:
        # 1. Ensure we have a metadata thread ID (create if new)
        if metadata_thread_id is None:
            default_name = _generate_default_thread_name(request.constitution_ids)
            metadata_thread_id = await metadata_manager.add_thread(name=default_name)
            print(f"Implicitly created new Thread {metadata_thread_id} with default name: '{default_name}'")
            # No previous messages for a new thread
        else:
            # Verify thread exists
            thread_info = await metadata_manager.get_thread(metadata_thread_id)
            if not thread_info: raise HTTPException(status_code=404, detail=f"Thread with ID {metadata_thread_id} not found.")

            # --- Load History for Existing Thread ---
            latest_checkpoint_thread_id = await metadata_manager.get_latest_checkpoint_thread_id(metadata_thread_id)
            if latest_checkpoint_thread_id:
                 print(f"Continuing Thread {metadata_thread_id}. Loading state from Checkpoint Thread ID: {latest_checkpoint_thread_id}")
                 config_prev = {"configurable": {"thread_id": latest_checkpoint_thread_id}}
                 checkpoint_tuple_prev = await checkpointer.aget_tuple(config_prev)
                 if checkpoint_tuple_prev and checkpoint_tuple_prev.checkpoint:
                      previous_messages = checkpoint_tuple_prev.checkpoint.get("channel_values", {}).get("messages", [])
                      print(f"Loaded {len(previous_messages)} previous messages.")
                 else:
                      print(f"Warning: Could not load previous state for {latest_checkpoint_thread_id}, continuing with current input only.")
            else:
                 print(f"No previous runs found for Thread {metadata_thread_id}. Starting with current input.")


        # 2. Generate a unique checkpoint_thread_id for this specific run
        # (We still use a unique ID here to store run-specific metadata like constitution)
        checkpoint_thread_id = f"thread_{metadata_thread_id}_run_{uuid.uuid4()}"
        print(f"Starting stream run for Thread {metadata_thread_id}, Checkpoint Thread ID: {checkpoint_thread_id}")

        # 3. Prepare input message list (History + New Input)
        input_messages_for_run = previous_messages + [current_input_message]

        # 4. Return the SSE response stream
        # stream_events now adds the run to the DB internally
        return EventSourceResponse(stream_events(
            metadata_thread_id=metadata_thread_id,
            checkpoint_thread_id=checkpoint_thread_id,
            input_messages=input_messages_for_run, # Pass combined list
            constitution_ids=request.constitution_ids,
            run_app=graph_app,
            checkpointer_instance=checkpointer, # Pass checkpointer instance
        ))

    except HTTPException: raise
    except Exception as e: print(f"Error setting up stream run for thread {request.thread_id}: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to initiate stream.")


# --- Compare Streaming Endpoint ---
# (Needs similar logic for loading previous state if comparing within an existing thread)
@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(
    request: CompareRunRequest,
    graph_app: Any = Depends(get_graph_app),
    inner_agent_app: Any = Depends(get_inner_agent_app), # Inject inner agent app
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer)
):
    """Handles streaming runs for comparing multiple constitution sets."""
    metadata_thread_id = request.thread_id
    current_input_message = HumanMessage(content=request.input.content)
    previous_messages: List[BaseMessage] = [] # History for compare runs

    try:
        # 1. Validate input
        if not request.input or not request.input.content: raise HTTPException(status_code=400, detail="Input content required.")
        effective_inner_app = await inner_agent_app # Resolve dependency
        if not request.constitution_sets and not effective_inner_app: raise HTTPException(status_code=400, detail="At least one set or inner agent required.")

        # 2. Ensure metadata thread ID (create if new)
        if metadata_thread_id is None:
            first_const_ids = request.constitution_sets[0].constitution_ids if request.constitution_sets else ['none']
            default_name = _generate_default_thread_name(first_const_ids) + " [Comparison]"
            metadata_thread_id = await metadata_manager.add_thread(name=default_name)
            print(f"Implicitly created new Thread {metadata_thread_id} for comparison: '{default_name}'")
            # No previous messages for a new thread
        else:
            # Verify thread exists and load history if continuing compare on existing thread
            thread_info = await metadata_manager.get_thread(metadata_thread_id)
            if not thread_info: raise HTTPException(status_code=404, detail=f"Thread with ID {metadata_thread_id} not found.")
            latest_checkpoint_thread_id = await metadata_manager.get_latest_checkpoint_thread_id(metadata_thread_id)
            if latest_checkpoint_thread_id:
                 print(f"Continuing Compare on Thread {metadata_thread_id}. Loading state from Checkpoint Thread ID: {latest_checkpoint_thread_id}")
                 config_prev = {"configurable": {"thread_id": latest_checkpoint_thread_id}}
                 checkpoint_tuple_prev = await checkpointer.aget_tuple(config_prev)
                 if checkpoint_tuple_prev and checkpoint_tuple_prev.checkpoint:
                      previous_messages = checkpoint_tuple_prev.checkpoint.get("channel_values", {}).get("messages", [])
                      print(f"Loaded {len(previous_messages)} previous messages for compare base.")
                 else: print(f"Warning: Could not load previous state for {latest_checkpoint_thread_id}.")
            else: print(f"No previous runs found for Thread {metadata_thread_id}.")


        # 3. Prepare runs to perform
        runs_to_perform: List[Tuple[str, List[str], str, Any]] = []
        compare_group_id = str(uuid.uuid4())
        input_messages_for_run = previous_messages + [current_input_message] # Base history + new input

        # Superego-involved runs
        for i, const_set in enumerate(request.constitution_sets):
            set_name = const_set.id or f"set_{i+1}"
            checkpoint_thread_id = f"compare_{compare_group_id}_{set_name}_{uuid.uuid4()}" # Ensure unique even if set_id repeats
            # Each compare run starts with the same combined input history
            runs_to_perform.append( (checkpoint_thread_id, const_set.constitution_ids, set_name, graph_app) )

        # Inner Agent Only run
        if effective_inner_app:
            inner_set_id = "inner_agent_only"
            inner_checkpoint_thread_id = f"compare_{compare_group_id}_{inner_set_id}_{uuid.uuid4()}"
            runs_to_perform.append( (inner_checkpoint_thread_id, [], inner_set_id, effective_inner_app) )
        else: print("Warning: Inner agent app not available, skipping inner_agent_only comparison run.")

        # 4. Return the SSE response stream
        # stream_compare_events needs modification to pass the full input message list
        return EventSourceResponse(stream_compare_events(
            metadata_thread_id=metadata_thread_id,
            input_messages_for_run=input_messages_for_run, # Pass combined list
            runs_to_perform=runs_to_perform,
            checkpointer_instance=checkpointer # Pass checkpointer instance
        ))

    except HTTPException: raise
    except Exception as e: print(f"Error setting up compare run for thread {request.thread_id}: {e}"); traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to initiate comparison stream.")


# --- Modified Compare Streaming Helper ---
async def stream_compare_events(
    metadata_thread_id: int,
    input_messages_for_run: List[BaseMessage], # Now receives the full list
    runs_to_perform: List[Tuple[str, List[str], str, Any]], # List of (checkpoint_thread_id, constitution_ids, set_id, run_app)
    checkpointer_instance: BaseCheckpointSaver # Receive checkpointer
) -> AsyncGenerator[ServerSentEvent, None]:
    """Runs multiple streams concurrently for comparison and multiplexes their events."""
    event_queue = asyncio.Queue()
    consumer_tasks = []
    active_stream_count = len(runs_to_perform)

    print(f"Compare: Starting {active_stream_count} parallel runs for Thread {metadata_thread_id}")

    for checkpoint_thread_id, constitution_ids, set_id, run_app in runs_to_perform:
        print(f"Compare: Launching Set='{set_id}', Checkpoint Thread='{checkpoint_thread_id}'")
        stream = stream_events(
            metadata_thread_id=metadata_thread_id,
            checkpoint_thread_id=checkpoint_thread_id,
            input_messages=input_messages_for_run, # Use the full input list for each branch
            constitution_ids=constitution_ids,
            run_app=run_app,
            checkpointer_instance=checkpointer_instance, # Pass it down
            set_id=set_id
        )
        task = asyncio.create_task(consume_and_forward_stream(stream, event_queue))
        consumer_tasks.append(task)

    # --- Multiplex events from the queue ---
    # (No changes needed in multiplexing logic)
    finished_streams = 0
    while finished_streams < active_stream_count:
        try:
            event = await event_queue.get()
            if event is None: finished_streams += 1; continue
            yield event
            event_queue.task_done()
        except asyncio.CancelledError: print("Compare event streaming cancelled."); break
        except Exception as e:
            print(f"Error processing compare event queue: {e}")
            yield ServerSentEvent(data=SSEEventData( type="error", node="compare_multiplexer", data=f"Compare error: {e}").model_dump_json())
            yield ServerSentEvent(data=SSEEventData( type="end", node="error", data=SSEEndData(thread_id=metadata_thread_id)).model_dump_json())

    print(f"Compare streaming finished for Thread {metadata_thread_id}.")
    for task in consumer_tasks:
         if not task.done(): task.cancel()
    await asyncio.gather(*consumer_tasks, return_exceptions=True)


# --- Main Execution ---
if __name__ == "__main__":
    # ... (uvicorn setup remains the same) ...
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"): print("WARNING: ANTHROPIC_API_KEY environment variable not set. LangGraph models may fail.")
    host = os.getenv("BACKEND_HOST", "0.0.0.0"); port = int(os.getenv("BACKEND_PORT", "8000")); reload = os.getenv("BACKEND_RELOAD", "true").lower() == "true"
    print(f"Starting Uvicorn server on {host}:{port} (Reload: {'enabled' if reload else 'disabled'})")
    uvicorn.run("backend_server_async:app", host=host, port=port, reload=reload, log_level="info")
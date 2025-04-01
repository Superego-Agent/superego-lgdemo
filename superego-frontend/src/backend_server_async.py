# backend_server_async.py

import os
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Literal, Union, AsyncGenerator, Tuple
import aiosqlite # Ensure aiosqlite is imported

# --- Third-party imports ---
from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# Langchain / Langgraph specific imports
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk, message_chunk_to_message
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple # Import CheckpointTuple
from langgraph.graph.message import add_messages
from langchain_core.runnables.utils import AddableDict # For accessing event data

# --- Project-specific imports ---
try:
    from config import CONFIG # Assume exists
    from constitution_utils import get_available_constitutions, get_combined_constitution_content # Assume exists
    from superego_core_async import create_models, create_workflow # Assume exists
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Ensure backend_server.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH.")
    import sys
    sys.exit(1)

# --- Globals ---
graph_app: Any = None
checkpointer: AsyncSqliteSaver = None # More specific type hint
inner_agent_app: Any = None

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_app, checkpointer, inner_agent_app
    print("Backend server starting up...")
    try:
        superego_model, inner_model = create_models()
        graph_app, checkpointer, inner_agent_app = await create_workflow(superego_model=superego_model, inner_model=inner_model)
        # Ensure checkpointer schema is created after connection
        if checkpointer and hasattr(checkpointer, 'setup'):
             await checkpointer.setup() # Explicitly call setup if needed by checkpointer implementation
        print("Models and graph loaded successfully.")
    except Exception as e:
        print(f"FATAL: Error during startup model/graph creation: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for startup errors
        raise RuntimeError("Failed to initialize LangGraph workflow") from e
    yield
    # --- Shutdown ---
    print("Backend server shutting down...")
    if checkpointer and hasattr(checkpointer, 'conn') and checkpointer.conn:
        try:
            print("Closing database connection...")
            await checkpointer.conn.close()
        except Exception as e:
            print(f"Warning: Error closing checkpointer connection: {e}")

# --- FastAPI App ---
app = FastAPI(title="Superego Backend", lifespan=lifespan)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models (Adjusted SSEEventData) ---
class ConstitutionItem(BaseModel): id: str; name: str; description: Optional[str] = None
class ThreadItem(BaseModel): thread_id: str; title: str
class HistoryMessage(BaseModel): id: str; sender: str; content: Any; timestamp: Optional[int] = None; node: Optional[str] = None; set_id: Optional[str] = None
class HistoryResponse(BaseModel): messages: List[HistoryMessage]
class NewThreadResponse(BaseModel): thread_id: str
class StreamRunInput(BaseModel): type: Literal["human"]; content: str
class StreamRunRequest(BaseModel): thread_id: Optional[str] = None; input: Optional[StreamRunInput] = None; constitution_ids: List[str] = ["none"]
class CompareRunSet(BaseModel): id: str; constitution_ids: List[str]
class CompareRunRequest(BaseModel): input: StreamRunInput; constitution_sets: List[CompareRunSet]
# Ensure backend models match frontend expectations
class SSEToolCallChunkData(BaseModel): id: Optional[str] = None; name: Optional[str] = None; args: Optional[str] = None;
class SSEToolCallData(BaseModel): name: str; args: Any
class SSEToolResultData(BaseModel): tool_name: str; result: str; is_error: bool; tool_call_id: Optional[str] = None # Added tool_call_id
class SSEEndData(BaseModel): thread_id: str
class SSEEventData(BaseModel): type: Literal["chunk", "ai_tool_chunk", "tool_result", "error", "end"]; node: Optional[str] = None; data: Union[str, SSEToolCallChunkData, SSEToolResultData, SSEEndData]; set_id: Optional[str] = None


# --- Helper Function for Standard Streaming ---
async def stream_events(
    thread_id: str,
    input_messages: Optional[List[BaseMessage]],
    constitution_ids: List[str],
    run_app: Any,
    set_id: Optional[str] = None
) -> AsyncGenerator[ServerSentEvent, None]:
    if not run_app:
        yield ServerSentEvent(data=SSEEventData(type="error", data="Graph app not initialized.", set_id=set_id).model_dump_json())
        return

    current_node_name: Optional[str] = None
    # Track last yielded text chunk to prevent duplicates
    last_yielded_text: Dict[Tuple[Optional[str], Optional[str]], str] = {}

    try:
        constitution_content_for_run, loaded_ids = get_combined_constitution_content(constitution_ids)
        requested_set = set(id for id in constitution_ids if id != "none")
        missing_in_run = requested_set - set(loaded_ids)
        if missing_in_run:
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="setup",
                data=f"Warning: Constitution(s) not found/loaded: {', '.join(missing_in_run)}. Running without.",
                set_id=set_id
            ).model_dump_json())

        config = {"configurable": {"thread_id": thread_id, "constitution_content": constitution_content_for_run}}
        stream_input = {'messages': input_messages} if input_messages else {}

        stream = run_app.astream_events(stream_input, config=config, version="v1")

        async for event in stream:
            event_type = event.get("event")
            event_name = event.get("name")
            tags = event.get("tags", [])
            event_data = event.get("data", {})

            # Node Name Tracking
            if event_type in ["on_chain_start", "on_llm_start", "on_tool_start"]:
                if event_name in ["superego", "inner_agent", "tools"]:
                    current_node_name = event_name
                else:
                    potential_node_tags = [tag for tag in tags if tag in ["superego", "inner_agent", "tools"]]
                    if potential_node_tags:
                        current_node_name = potential_node_tags[-1]

            yield_key = (current_node_name, set_id)

            sse_payload_data: Any = None
            sse_event_type: Optional[str] = None

            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if isinstance(chunk, AIMessageChunk):
                    # Text Content Extraction
                    text_content = ""
                    if isinstance(chunk.content, str): text_content = chunk.content
                    elif isinstance(chunk.content, list):
                        for item in chunk.content:
                            if isinstance(item, dict):
                                if item.get("type") == "text": text_content += item.get("text", "")
                                elif item.get("type") == "content_block_delta":
                                    delta = item.get("delta", {});
                                    if delta.get("type") == "text_delta": text_content += delta.get("text", "")
                    # Yield Text Chunk (with dedupe)
                    if text_content:
                        last_text = last_yielded_text.get(yield_key, None)
                        if text_content != last_text:
                            sse_payload_text = SSEEventData(type="chunk", node=current_node_name, data=text_content, set_id=set_id)
                            yield ServerSentEvent(data=sse_payload_text.model_dump_json())
                            last_yielded_text[yield_key] = text_content

                    # Tool Call Chunk Extraction
                    tool_chunks = getattr(chunk, 'tool_call_chunks', [])
                    if tool_chunks:
                        for tc_chunk in tool_chunks:
                            # Ensure tool call ID is included in data
                            chunk_data = SSEToolCallChunkData(
                                id=tc_chunk.get("id"), # Pass the ID
                                name=tc_chunk.get("name"),
                                args=tc_chunk.get("args")
                            )
                            sse_payload_tool = SSEEventData(type="ai_tool_chunk", node=current_node_name, data=chunk_data, set_id=set_id)
                            yield ServerSentEvent(data=sse_payload_tool.model_dump_json())

            # Tool Result Handling
            elif event_type == "on_tool_end":
                 output_str = str(event_data.get("output", "")); tool_func_name = event.get("name"); is_error = isinstance(event_data.get("output"), Exception)
                 # Extract tool_call_id if available (depends on LangGraph version/event structure)
                 tool_call_id = None
                 if isinstance(event_data.get("parent_ids"), list) and len(event_data["parent_ids"]) > 0:
                      # Heuristic: LangChain often includes the triggering tool call ID in parent_ids
                      # This might need adjustment if internal structure changes
                      # Look specifically for IDs starting with 'toolu_' if that's the format
                      possible_ids = [pid for pid in event_data["parent_ids"] if isinstance(pid, str) and pid.startswith("toolu_")]
                      if possible_ids:
                          tool_call_id = possible_ids[-1] # Assume last one is most relevant

                 sse_event_type = "tool_result"
                 sse_payload_data = SSEToolResultData(tool_name=tool_func_name, result=output_str, is_error=is_error, tool_call_id=tool_call_id)


            # Yield distinct tool_result events
            if sse_event_type and sse_payload_data:
                sse_payload = SSEEventData(type=sse_event_type, node=current_node_name, data=sse_payload_data, set_id=set_id)
                yield ServerSentEvent(data=sse_payload.model_dump_json())

        yield ServerSentEvent(data=SSEEventData(type="end", node=current_node_name or "graph", data=SSEEndData(thread_id=thread_id), set_id=set_id).model_dump_json())
    except Exception as e: print(f"Stream Error: {e}"); import traceback; traceback.print_exc(); yield ServerSentEvent(data=SSEEventData(type="error", node=current_node_name or "graph", data=f"Streaming error: {str(e)}", set_id=set_id).model_dump_json())


# --- API Endpoints ---
@app.get("/api/constitutions")
async def get_constitutions_endpoint():
    try:
        constitutions_dict = get_available_constitutions();
        if "none" not in constitutions_dict: constitutions_dict["none"] = {"name": "None", "description": "No constitution"}
        elif not isinstance(constitutions_dict["none"], dict): constitutions_dict["none"] = {"name": "None", "description": str(constitutions_dict["none"])}
        response_items = [ConstitutionItem(id=k, name=v.get('name', k.replace('_', ' ').title()), description=v.get('description')) for k, v in constitutions_dict.items() if isinstance(v,dict)]
        return response_items
    except Exception as e: print(f"Error loading constitutions: {e}"); import traceback; traceback.print_exc(); raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")

@app.get("/api/threads")
async def get_threads_endpoint():
    if not checkpointer or not hasattr(checkpointer, 'conn'): raise HTTPException(status_code=500, detail="Checkpointer missing")
    thread_items = []
    try:
        # Use direct DB query
        query = "SELECT DISTINCT thread_id FROM checkpoints"; conn = checkpointer.conn
        distinct_thread_ids = [row[0] async for row in await conn.execute(query) if row and row[0]]
        limit = 100; distinct_thread_ids.sort(reverse=True) # Basic sort
        for thread_id in distinct_thread_ids[:limit]: thread_items.append(ThreadItem(thread_id=thread_id, title=f"Chat {thread_id[:8]}"))
        return thread_items
    except aiosqlite.OperationalError as db_err:
        print(f"DB error listing threads: {db_err}"); import traceback; traceback.print_exc()
        if "no such table" in str(db_err).lower(): print("Checkpoints table likely missing."); return []
        raise HTTPException(status_code=500, detail=f"DB error: {db_err}")
    except Exception as e: print(f"Error listing threads: {e}"); import traceback; traceback.print_exc(); raise HTTPException(status_code=500, detail="Failed to list threads")

@app.get("/api/threads/{thread_id}/history")
async def get_thread_history_endpoint(thread_id: str = FastApiPath(...)):
    if not checkpointer: raise HTTPException(status_code=500, detail="Checkpointer missing"); config = {"configurable": {"thread_id": thread_id}}
    try:
        try: uuid.UUID(thread_id, version=4)
        except ValueError: raise HTTPException(status_code=400, detail="Invalid thread ID")
        checkpoint_tuple = await checkpointer.get(config) # get IS async
        history_messages: List[HistoryMessage] = []
        if checkpoint_tuple:
            messages_from_state = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            base_timestamp_ms = int(checkpoint_tuple.checkpoint["ts"].timestamp() * 1000) if checkpoint_tuple.checkpoint.get("ts") else None
            for i, msg in enumerate(messages_from_state):
                sender = "system"; node = getattr(msg, 'name', None); content = msg.content
                tool_calls_for_history = []
                # Check for tool calls on AIMessage and add to content for simple history display
                if isinstance(msg, AIMessage):
                     sender = "ai"
                     # If AIMessage has tool_calls attribute, format them
                     if tool_calls := getattr(msg, "tool_calls", None):
                         tool_calls_for_history = tool_calls # Store structured if needed later
                         # Simple text representation for history 'content' field:
                         calls_str = "\n".join([f"-> Called Tool: {tc['name']}({json.dumps(tc['args'])})" for tc in tool_calls])
                         if isinstance(content, str): content += f"\n{calls_str}"
                         else: content = str(content) + f"\n{calls_str}" # Append to stringified content
                elif isinstance(msg, HumanMessage): sender = "human"
                elif isinstance(msg, ToolMessage): sender = "tool"; node = "tools" # Still represent original ToolMessage

                msg_timestamp = base_timestamp_ms + i if base_timestamp_ms is not None else None
                # Here content has tool calls appended for AI messages
                history_messages.append(HistoryMessage(id=f"{thread_id}-{i}", sender=sender, content=content, timestamp=msg_timestamp, node=node))
                # If structured tool calls needed in history response, modify HistoryMessage model
        return HistoryResponse(messages=history_messages)
    except HTTPException: raise
    except Exception as e: print(f"Error getting history {thread_id}: {e}"); import traceback; traceback.print_exc(); raise HTTPException(status_code=500, detail="Load history failed")

@app.post("/api/threads")
async def create_thread_endpoint():
    if not checkpointer: raise HTTPException(status_code=500, detail="Checkpointer missing"); new_thread_id = str(uuid.uuid4()); print(f"Created new thread ID: {new_thread_id}"); return NewThreadResponse(thread_id=new_thread_id)

@app.post("/api/runs/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    thread_id = request.thread_id; input_messages = None;
    if not thread_id: thread_id = str(uuid.uuid4()); print(f"Starting new stream: {thread_id}")
    else: print(f"Continuing stream: {thread_id}")
    if request.input: input_messages = [HumanMessage(content=request.input.content)]
    return EventSourceResponse(stream_events(thread_id=thread_id, input_messages=input_messages, constitution_ids=request.constitution_ids, run_app=graph_app))

# --- Compare Streaming Helper and Endpoint ---
async def stream_compare_events(input_message: BaseMessage, constitution_sets: List[CompareRunSet]) -> AsyncGenerator[ServerSentEvent, None]:
    compare_run_uuid = str(uuid.uuid4())[:8]; all_tasks = []
    for i, const_set in enumerate(constitution_sets): set_name = const_set.id; temp_thread_id = f"compare_{compare_run_uuid}_{set_name}"; print(f"Compare: Set='{set_name}', Thread='{temp_thread_id}'"); task = asyncio.create_task(consume_and_forward_stream(stream_events(thread_id=temp_thread_id,input_messages=[input_message], constitution_ids=const_set.constitution_ids, run_app=graph_app, set_id=set_name))); all_tasks.append(task)
    inner_set_id = "inner_agent_only"; inner_temp_thread_id = f"compare_{compare_run_uuid}_{inner_set_id}"; print(f"Compare: Set='{inner_set_id}', Thread='{inner_temp_thread_id}'"); inner_task = asyncio.create_task(consume_and_forward_stream(stream_events(thread_id=inner_temp_thread_id, input_messages=[input_message], constitution_ids=[], run_app=inner_agent_app, set_id=inner_set_id))); all_tasks.append(inner_task)
    results_queues = await asyncio.gather(*all_tasks); active_queues = list(results_queues)
    while active_queues:
        get_tasks = [asyncio.create_task(q.get()) for q in active_queues]; done, pending = await asyncio.wait(get_tasks, return_when=asyncio.FIRST_COMPLETED)
        for future in done:
            try:
                event = future.result()
                if event is None:
                    # Find and remove the queue corresponding to this future
                    for i, task in enumerate(get_tasks):
                        if task == future:
                            active_queues.pop(i)
                            break
                    continue
                yield event
            except asyncio.QueueEmpty: pass
            except Exception as e: print(f"Error processing compare event: {e}"); yield ServerSentEvent(data=SSEEventData(type="error", node="compare_multiplexer", data=f"Compare error: {e}").model_dump_json())

async def consume_and_forward_stream(stream: AsyncGenerator[ServerSentEvent, None]) -> asyncio.Queue:
    queue = asyncio.Queue(); processed = False
    async for event in stream: await queue.put(event); processed = True; await queue.put(None); return queue

@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(request: CompareRunRequest):
   input_message = HumanMessage(content=request.input.content); return EventSourceResponse(stream_compare_events(input_message=input_message, constitution_sets=request.constitution_sets))

# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"): print("WARNING: ANTHROPIC_API_KEY missing")
    host = os.getenv("HOST", "0.0.0.0"); port = int(os.getenv("PORT", "8000")); reload = os.getenv("RELOAD", "true").lower() == "true"
    print(f"Starting server on {host}:{port} with reload={'enabled' if reload else 'disabled'}")
    uvicorn.run("backend_server_async:app", host=host, port=port, reload=reload)

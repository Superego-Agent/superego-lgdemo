# backend_server.py (Updated with streaming endpoints)

import os
import uuid
import json
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Literal, Union, AsyncGenerator

# --- Third-party imports ---
from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# Langchain / Langgraph specific imports
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk, message_chunk_to_message
# Note: Ensure all necessary message types are handled or imported
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.message import add_messages # Utility for state updates if needed

# --- Project-specific imports ---
try:
    from config import CONFIG #
    from constitution_utils import get_available_constitutions, get_combined_constitution_content #
    from superego_core import create_models, create_workflow #
    # Import CliState definition if needed for type hints (though not strictly necessary here)
    # from cli import CliState
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Ensure backend_server.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH.")
    import sys
    sys.exit(1)

# --- Globals (populated during startup lifespan) ---
graph_app: Any = None
checkpointer: BaseCheckpointSaver = None
inner_agent_app: Any = None

# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_app, checkpointer, inner_agent_app
    print("Backend server starting up...")
    try:
        superego_model, inner_model = create_models() #
        graph_app, checkpointer, inner_agent_app = create_workflow(superego_model=superego_model, inner_model=inner_model) #
        print("Models and graph loaded successfully.")
    except Exception as e:
        print(f"FATAL: Error during startup model/graph creation: {e}")
        raise RuntimeError("Failed to initialize LangGraph workflow") from e
    yield
    # --- Shutdown ---
    print("Backend server shutting down...")
    if checkpointer and hasattr(checkpointer, 'conn') and checkpointer.conn:
        try:
            print("Closing database connection...")
            checkpointer.conn.close() #
        except Exception as e:
            print(f"Warning: Error closing checkpointer connection: {e}")

# --- FastAPI App Initialization ---
app = FastAPI(title="Superego Backend", lifespan=lifespan)

# --- CORS Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
# (Keep existing models: ConstitutionItem, ThreadItem, HistoryMessage, HistoryResponse, NewThreadResponse)

class StreamRunInput(BaseModel):
    type: Literal["human"]
    content: str

class StreamRunRequest(BaseModel):
    thread_id: Optional[str] = None
    input: Optional[StreamRunInput] = None
    constitution_ids: List[str] = ["none"]

class CompareRunSet(BaseModel):
    id: str # Frontend generated ID
    constitution_ids: List[str]

class CompareRunRequest(BaseModel):
    input: StreamRunInput
    constitution_sets: List[CompareRunSet]

# SSE Event Data Model
class SSEEventData(BaseModel):
    type: Literal["chunk", "tool_call", "tool_result", "error", "end"]
    node: Optional[str] = None # Node where event originated
    data: Any # Specific data depends on the event type
    set_id: Optional[str] = None # For compare mode

# --- Helper Function for Standard Streaming ---

async def stream_events(
    thread_id: str,
    input_messages: Optional[List[BaseMessage]],
    constitution_ids: List[str],
    run_app: Any, # Can be graph_app or inner_agent_app
    set_id: Optional[str] = None # Added for compare mode reuse
) -> AsyncGenerator[ServerSentEvent, None]:
    """Streams graph events as Server-Sent Events."""
    if not run_app:
        yield ServerSentEvent(data=SSEEventData(type="error", data="Graph app not initialized.", set_id=set_id).model_dump_json())
        return

    try:
        # 1. Get constitution content
        constitution_content_for_run, loaded_ids = get_combined_constitution_content(constitution_ids) #
        # Optionally, yield a warning if some requested IDs weren't loaded
        requested_set = set(id for id in constitution_ids if id != "none")
        missing_in_run = requested_set - set(loaded_ids)
        if missing_in_run:
            yield ServerSentEvent(data=SSEEventData(
                type="error", # Or a specific 'warning' type?
                node="setup",
                data=f"Warning: Constitution(s) not found/loaded: {', '.join(missing_in_run)}. Running without.",
                set_id=set_id
            ).model_dump_json())

        # 2. Prepare config
        config = {"configurable": {"thread_id": thread_id, "constitution_content": constitution_content_for_run}}

        # 3. Prepare input dictionary for stream
        stream_input = {'messages': input_messages} if input_messages else None # LangGraph expects dict or None

        # 4. Stream using astream_events for full event data, including metadata
        #    Alternative: .stream(..., stream_mode="messages") gives BaseMessage chunks directly
        stream = run_app.astream_events(stream_input, config=config, version="v1") # Use async stream

        async for event in stream:
            event_type = event.get("event")
            event_name = event.get("name") # Node name often in 'name'
            event_data = event.get("data", {})
            tags = event.get("tags", [])

            # Determine the node (can be in name or tags)
            node = event_name or next((tag for tag in tags if tag not in ['seq:step', 'graph', 'chain']), None) or "graph"

            sse_payload = None

            # --- Handle different langgraph event types ---
            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                     # Filter out empty chunks from some models
                    if chunk.content:
                        sse_payload = SSEEventData(type="chunk", node=node, data=chunk.content, set_id=set_id)

            elif event_type == "on_tool_start":
                 # Potentially useful, but tool_end has the result
                 # tool_input = event_data.get("input") # Careful with sensitive data
                 tool_name = event_data.get("name")
                 sse_payload = SSEEventData(type="tool_call", node=node, data={"name": tool_name, "args": "Starting..."}, set_id=set_id) # Simplified

            elif event_type == "on_tool_end":
                 tool_output = event_data.get("output")
                 tool_name = event_data.get("name")
                 # Check for potential errors (Langchain might structure errors differently)
                 is_error = isinstance(tool_output, Exception) or event_data.get("error") is not None

                 sse_payload = SSEEventData(
                     type="tool_result",
                     node=node,
                     data={"tool_name": tool_name, "result": str(tool_output), "is_error": is_error},
                     set_id=set_id
                 )

            # Add handling for other event types ('on_chain_stream', 'on_retriever_stream', etc.) if needed

            # Yield the formatted event
            if sse_payload:
                yield ServerSentEvent(data=sse_payload.model_dump_json())

        # Signal the end of the stream for this run
        yield ServerSentEvent(data=SSEEventData(type="end", node="graph", data={"thread_id": thread_id}, set_id=set_id).model_dump_json())

    except Exception as e:
        print(f"Error during streaming for thread {thread_id}: {e}")
        import traceback
        traceback.print_exc()
        yield ServerSentEvent(data=SSEEventData(type="error", node="graph", data=f"Streaming error: {e}", set_id=set_id).model_dump_json())


# --- API Endpoints ---
# (Keep existing endpoints: /api/constitutions, /api/threads, /api/threads/{thread_id}/history)

@app.post("/api/runs/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    """Handles standard chat streaming requests."""
    thread_id = request.thread_id if request.thread_id else str(uuid.uuid4())

    input_messages: Optional[List[BaseMessage]] = None
    if request.input:
        input_messages = [HumanMessage(content=request.input.content)]

    return EventSourceResponse(stream_events(
        thread_id=thread_id,
        input_messages=input_messages,
        constitution_ids=request.constitution_ids,
        run_app=graph_app # Use the main graph app
    ))

# --- Helper Function for Compare Streaming ---

async def stream_compare_events(
    input_message: BaseMessage,
    constitution_sets: List[CompareRunSet],
    # original_thread_id: Optional[str] = None # If needed for context
) -> AsyncGenerator[ServerSentEvent, None]:
    """Runs compare mode and streams multiplexed events."""

    compare_run_uuid = str(uuid.uuid4())[:8]
    all_tasks = []

    # --- Prepare Superego Runs ---
    for i, const_set in enumerate(constitution_sets):
        set_name = const_set.id # Use frontend provided ID
        # Create unique thread ID for this specific compare run to avoid state collision
        temp_thread_id = f"compare_{compare_run_uuid}_{set_name}"

        print(f"Compare Task: Set='{set_name}', Thread='{temp_thread_id}', ConstIDs='{const_set.constitution_ids}'")

        # Create a task for each constitution set run using the main graph app
        task = asyncio.create_task(
            # Need to consume the generator from stream_events within the task
            consume_and_forward_stream(
                stream_events(
                    thread_id=temp_thread_id,
                    input_messages=[input_message], # Send same input to each
                    constitution_ids=const_set.constitution_ids,
                    run_app=graph_app, # Use main app
                    set_id=set_name # Pass the set ID
                )
            )
        )
        all_tasks.append(task)

    # --- Prepare Inner Agent Only Run ---
    inner_set_id = "inner_agent_only"
    inner_temp_thread_id = f"compare_{compare_run_uuid}_{inner_set_id}"
    print(f"Compare Task: Set='{inner_set_id}', Thread='{inner_temp_thread_id}', ConstIDs='[]'")
    inner_task = asyncio.create_task(
        consume_and_forward_stream(
            stream_events(
                thread_id=inner_temp_thread_id,
                input_messages=[input_message],
                constitution_ids=[], # No constitution for inner agent run
                run_app=inner_agent_app, # Use the inner agent app
                set_id=inner_set_id
            )
        )
    )
    all_tasks.append(inner_task)

    # --- Multiplex Results ---
    # Use asyncio.gather to run all stream consumers concurrently
    # Forward events as they arrive from any stream
    results_queues = [await task for task in all_tasks] # Each task returns a queue

    active_queues = list(results_queues)
    while active_queues:
        # Wait for the next event from any active queue
        done, pending = await asyncio.wait(
            [asyncio.create_task(q.get()) for q in active_queues],
            return_when=asyncio.FIRST_COMPLETED
        )

        for future in done:
            try:
                event = future.result()
                if event is None: # Sentinel value indicating stream end
                    # Find which queue finished and remove it
                    for i, q in enumerate(active_queues):
                         # Rough way to find the queue, relies on task finishing means queue is empty + sentinel
                         # A better approach might involve associating queues with tasks more directly
                         if q._queue[0] is None: # Check if sentinel is next (internal access, risky)
                              active_queues.pop(i)
                              break
                    continue
                yield event # Forward the actual SSE event
            except asyncio.QueueEmpty:
                 # This shouldn't happen with the await asyncio.wait logic, but handle defensively
                 pass
            except Exception as e:
                print(f"Error processing compare stream event: {e}")
                # Yield an error specific to this stream multiplexing if needed
                yield ServerSentEvent(data=SSEEventData(type="error", node="compare_multiplexer", data=f"Compare processing error: {e}").model_dump_json())

        # Re-queue the tasks for queues that haven't finished
        # This logic is tricky with Queue.get(), asyncio.wait might be sufficient
        # Let's simplify: rely on the sentinel to remove finished queues

        # If a task failed unexpectedly, remove its queue
        # (Error handling needs refinement)


async def consume_and_forward_stream(stream: AsyncGenerator[ServerSentEvent, None]) -> asyncio.Queue:
    """Helper to run a stream generator and put its items into a queue."""
    queue = asyncio.Queue()
    async for event in stream:
        await queue.put(event)
    await queue.put(None) # Sentinel value to indicate the stream is done
    return queue


@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(request: CompareRunRequest):
    """Handles compare mode streaming requests."""
    input_message = HumanMessage(content=request.input.content)

    return EventSourceResponse(stream_compare_events(
        input_message=input_message,
        constitution_sets=request.constitution_sets
        # original_thread_id=request.original_thread_id # Pass if needed
    ))


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("FATAL: ANTHROPIC_API_KEY environment variable not set.") #
    else:
        # Use reload=True for development, but turn off for production
        uvicorn.run("backend_server:app", host="0.0.0.0", port=8000, reload=True)
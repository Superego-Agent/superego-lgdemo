import json
import traceback
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from langchain_core.messages import (
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langgraph.checkpoint.base import BaseCheckpointSaver
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from backend_models import (  # Added HumanApiMessageModel; Added missing SSE types
    CheckpointConfigurable,
    HumanApiMessageModel,
    RunConfig,
    SSEChunkData,
    SSEEndData,
    SSEErrorData,
    SSERunStartData,
    SSEToolCallChunkData,
    SSEToolResultData,
    StreamRunRequest,
)

# Assuming this is accessible
from constitution_utils import get_constitution_content
from keystore import keystore
from utils import prepare_sse_event  # Import the missing helper

# Create the router instance
router = APIRouter(prefix="/api/runs", tags=["runs"])
# Add attributes to hold instances passed from the main app
# These attributes are set during app startup (lifespan event).
router.graph_app_instance = None
router.checkpointer_instance = None


# --- Helper Function for Standard Streaming ---
# Moved from backend_server_async.py
async def stream_events(
    # The unique LangGraph thread ID (string UUID) for this specific run
    thread_id: str,
    input_messages: List[BaseMessage],
    run_config: RunConfig,  # Use the RunConfig model
    # Pass the full configurable object
    configurable_metadata: CheckpointConfigurable,
    # The compiled LangGraph app to run (passed via router attribute)
    run_app: Any,
    checkpointer: BaseCheckpointSaver,  # Passed via router attribute
    set_id: Optional[str] = None,  # Identifier for compare mode sets
) -> AsyncGenerator[ServerSentEvent, None]:
    """Generates Server-Sent Events for a single LangGraph run."""
    if not run_app or not checkpointer:
        error_msg = "Graph app or checkpointer not initialized."
        error_data_payload = SSEErrorData(node="setup", error=error_msg)
        yield await prepare_sse_event(
            "error", data_payload=error_data_payload, thread_id=thread_id
        )
        return

    current_node_name: Optional[str] = None
    last_yielded_text: Dict[Tuple[Optional[str], Optional[str]], str] = {}
    final_checkpoint_id: Optional[str] = None

    try:
        # (content, title, level)
        processed_modules: List[Tuple[str, str, int]] = []
        missing_ids: List[str] = []

        for module in run_config.configuredModules:
            content = module.text
            if (
                module.relativePath
            ):  # If relativePath is provided, try fetching from file
                try:
                    content = get_constitution_content(module.relativePath)
                except Exception as e:
                    print(
                        f"Error reading constitution from file {module.relativePath}: {e}"
                    )
                    content = None  # Handle file reading errors gracefully

            if content is None and module.text:
                content = module.text  # Use provided text if available

            if content is not None:
                processed_modules.append(
                    (content, module.title, module.adherence_level)
                )
            else:
                missing_ids.append(
                    module.relativePath or "unknown"
                )  # Track IDs that couldn't be loaded

        # Generate constitution text and adherence report lines using list comprehensions
        constitution_texts = [content for content, _, _ in processed_modules]
        adherence_report_lines = (
            ["# User-specified Adherence Levels"]
            + [
                f"- {title}: {level}/5{' (Default)' if level == 3 else ''}"
                for _, title, level in processed_modules
            ]
            if processed_modules
            else []  # Add header only if there are modules
        )

        base_constitution_content = "\n\n---\n\n".join(constitution_texts)
        adherence_report_text = "\n".join(adherence_report_lines)
        final_constitution_content = base_constitution_content
        if len(adherence_report_lines) > 1:
            final_constitution_content += f"\n\n---\n\n{adherence_report_text}"

        if missing_ids:
            error_msg = f"Warning: Constitution ID(s) not found/loaded: {', '.join(missing_ids)}. Running without them."
            error_data_payload = SSEErrorData(node="setup", error=error_msg)
            yield await prepare_sse_event(
                "error", data_payload=error_data_payload, thread_id=thread_id
            )

        # --- Yield run_start event ---
        # Prepare data for the run_start event
        # Explicitly add nodeId='user' when creating HumanApiMessageModel
        initial_messages_adapted = []
        for msg in input_messages:
            if isinstance(msg, HumanMessage):
                msg_dict = msg.model_dump()
                msg_dict["nodeId"] = "user"  # Add the required nodeId
                initial_messages_adapted.append(HumanApiMessageModel(**msg_dict))
            # Add handling for other potential initial message types if necessary

        run_start_data = SSERunStartData(
            thread_id=thread_id,
            runConfig=run_config,
            initialMessages=initial_messages_adapted,
            node="setup",
        )
        # Use the helper to create and yield the event
        start_event = await prepare_sse_event(
            "run_start", data_payload=run_start_data, thread_id=thread_id
        )
        yield start_event
        # --- End run_start event ---

        config_for_run = configurable_metadata.model_dump()
        config_for_run["constitution_content"] = final_constitution_content

        config_payload = {"configurable": config_for_run}
        stream_input = {"messages": input_messages}

        stream = run_app.astream_events(
            stream_input, config=config_payload, version="v1"
        )

        async for event in stream:
            event_type = event.get("event")
            event_name = event.get("name")
            tags = event.get("tags", [])
            event_data = event.get("data", {})
            run_id = event.get("run_id")

            if run_id:
                final_checkpoint_id = str(run_id)

            potential_node_tags = [
                tag for tag in tags if tag in ["superego", "inner_agent", "tools"]
            ]
            if event_name in ["superego", "inner_agent", "tools"]:
                current_node_name = event_name
            elif potential_node_tags:
                current_node_name = potential_node_tags[-1]

            yield_key = (current_node_name, set_id)

            if event_type == "on_chat_model_stream" and isinstance(
                event_data.get("chunk"), AIMessageChunk
            ):
                chunk: AIMessageChunk = event_data["chunk"]
                text_content = ""
                if isinstance(chunk.content, str):
                    text_content = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_content += item.get("text", "")
                            elif (
                                item.get("type") == "content_block_delta"
                                and item.get("delta", {}).get("type") == "text_delta"
                            ):
                                text_content += item.get("delta", {}).get("text", "")

                if text_content:
                    last_text = last_yielded_text.get(yield_key, "")
                    if text_content != last_text:
                        # Use helper for chunk event
                        chunk_data_payload = SSEChunkData(
                            node=current_node_name or "unknown_node",
                            content=text_content,
                        )
                        yield await prepare_sse_event(
                            "chunk",
                            data_payload=chunk_data_payload,
                            thread_id=thread_id,
                        )
                        last_yielded_text[yield_key] = text_content

            if event_type == "on_chat_model_stream" and isinstance(
                event_data.get("chunk"), AIMessageChunk
            ):
                chunk_for_tools: AIMessageChunk = event_data["chunk"]
                tool_chunks = getattr(chunk_for_tools, "tool_call_chunks", [])
                if tool_chunks:
                    for tc_chunk in tool_chunks:
                        args_value = tc_chunk.get("args")
                        args_str: Optional[str] = None
                        if args_value is not None:
                            if isinstance(args_value, str):
                                args_str = args_value
                            else:
                                try:
                                    args_str = json.dumps(args_value)
                                except Exception:
                                    args_str = str(args_value)

                        chunk_data = SSEToolCallChunkData(
                            node=current_node_name or "unknown_node",  # Add node field
                            id=tc_chunk.get("id"),
                            name=tc_chunk.get("name"),
                            args=args_str,
                        )
                        # Use helper for ai_tool_chunk event
                        yield await prepare_sse_event(
                            "ai_tool_chunk",
                            data_payload=chunk_data,
                            thread_id=thread_id,
                        )

            elif event_type == "on_tool_end":
                tool_output = event_data.get("output")
                try:
                    output_str = (
                        json.dumps(tool_output)
                        if not isinstance(tool_output, str)
                        else tool_output
                    )
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

                # Construct cleaner payload: Use 'content' instead of 'result'
                # Ensure tool_call_id is correctly extracted and passed.
                # --- Start: Extract content from tool_output ---
                final_content_string = (
                    "Error processing tool output."  # Default/fallback
                )
                if isinstance(tool_output, ToolMessage):
                    final_content_string = tool_output.content
                elif isinstance(
                    tool_output, str
                ):  # Keep basic string handling just in case
                    final_content_string = tool_output
                else:
                    # Fallback for other unexpected types
                    try:
                        final_content_string = str(tool_output)
                    except Exception:
                        pass  # Keep the default error message if str() fails
                # --- End: Extract content from tool_output ---
                sse_payload_data = SSEToolResultData(
                    node="tools",  # Add node field
                    tool_name=tool_func_name or "unknown_tool",
                    content=final_content_string,  # Use the extracted content
                    is_error=is_error,
                    tool_call_id=tool_call_id,  # Pass the extracted ID
                )
                # Use helper for tool_result event
                yield await prepare_sse_event(
                    "tool_result", data_payload=sse_payload_data, thread_id=thread_id
                )

        # --- Yield end event using helper ---
        end_data = SSEEndData(
            node=current_node_name or "graph",
            thread_id=thread_id,
            checkpoint_id=final_checkpoint_id,
        )  # Add node field
        end_event = await prepare_sse_event(
            "end", data_payload=end_data, thread_id=thread_id
        )  # Removed node, set_id args
        yield end_event
        # --- End end event ---

    except Exception as e:
        print(f"Stream Error (Thread ID: {thread_id}, Set: {set_id}): {e}")
        traceback.print_exc()
        # --- Yield error and end events using helper ---
        error_msg = f"Streaming error: {str(e)}"
        error_data_payload = SSEErrorData(
            node=current_node_name or "graph", error=error_msg
        )
        error_event = await prepare_sse_event(
            "error", data_payload=error_data_payload, thread_id=thread_id
        )  # Removed node, set_id args
        yield error_event

        # Also yield the 'end' event after the error
        end_data_on_error = SSEEndData(
            node="error", thread_id=thread_id, checkpoint_id=final_checkpoint_id
        )  # Add node field
        final_end_event = await prepare_sse_event(
            "end", data_payload=end_data_on_error, thread_id=thread_id
        )  # Removed node, set_id args
        yield final_end_event
        # --- End error/end events ---


# --- Wrapper for Streaming  ---
# This wrapper is now primarily just to handle the specific case of a *new* thread ID
# It calls the main stream_events which now handles the run_start event itself.
async def stream_run_for_new_thread(
    new_thread_id: str,  # The newly generated thread_id
    input_messages: List[BaseMessage],
    run_config: RunConfig,  # Use RunConfig
    configurable_metadata: CheckpointConfigurable,
    run_app: Any,  # Passed via router attribute
    checkpointer: BaseCheckpointSaver,  # Passed via router attribute
) -> AsyncGenerator[ServerSentEvent, None]:
    """Streams events for a newly created thread."""
    # The run_start event is now handled within stream_events
    print(f"Streaming for NEW Thread ID: {new_thread_id}")
    async for event in stream_events(
        thread_id=new_thread_id,
        input_messages=input_messages,
        run_config=run_config,
        configurable_metadata=configurable_metadata,
        run_app=run_app,
        checkpointer=checkpointer,
        set_id=None,
    ):
        yield event


# --- Run Endpoint ---
# Moved from backend_server_async.py
@router.post("/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    """Handles streaming runs for a single thread (normal chat)."""
    graph_app = router.graph_app_instance  # Access passed instance
    checkpointer = router.checkpointer_instance  # Access passed instance

    if not graph_app or not checkpointer:
        raise HTTPException(
            status_code=500, detail="Backend application components not initialized."
        )

    try:
        input_data = request.input
        configurable_data = request.configurable
        thread_id = configurable_data.thread_id
        run_config = configurable_data.runConfig
        session_id = request.session_id

        # Get the session ID from the request if available
        # session_id = getattr(request, "session_id", None)

        # If session_id is not provided in the request, try to extract it from headers or cookies
        if not session_id and request.headers.get("x-session-id"):
            session_id = request.headers.get("x-session-id")

        # If we have a session ID, get the API key from the keystore
        api_key = None
        if session_id:
            api_key = keystore.get_key(session_id)
            if api_key:
                print(f"Using API key from keystore for session {session_id}")

        if not input_data or not input_data.content:
            raise HTTPException(status_code=400, detail="Input content is required.")
        input_messages = [HumanMessage(content=input_data.content)]

        if thread_id is None:
            new_thread_id = str(uuid.uuid4())
            print(
                f"Received request for new thread. Generated Thread ID: {new_thread_id}"
            )
            configurable_data_with_id = configurable_data.model_copy(
                update={"thread_id": new_thread_id}
            )

            # Import here to avoid circular imports
            from superego_core_async import create_models

            # If we have an API key from the session, create new models with it
            if api_key:
                # Create new models with the API key
                superego_model, inner_model = create_models(api_key)

                # If models were created successfully, use them for this request
                if superego_model is not None and inner_model is not None:
                    print(f"Created new models with API key from session {session_id}")
                    # TODO: Create a new workflow with these models if needed

            # Call the renamed helper for new threads
            event_stream = stream_run_for_new_thread(
                new_thread_id=new_thread_id,
                input_messages=input_messages,
                run_config=run_config,
                configurable_metadata=configurable_data_with_id,  # Pass the one with the ID set
                run_app=graph_app,  # Pass instance
                checkpointer=checkpointer,  # Pass instance
            )
        else:
            existing_thread_id = thread_id
            print(f"Received request to continue Thread ID: {existing_thread_id}")
            event_stream = stream_events(
                thread_id=existing_thread_id,
                input_messages=input_messages,
                run_config=run_config,
                configurable_metadata=configurable_data,
                run_app=graph_app,  # Pass instance
                checkpointer=checkpointer,  # Pass instance
            )

        return EventSourceResponse(event_stream)

    except HTTPException:
        raise
    except Exception as e:
        # Use thread_id from original request if available for logging
        log_thread_id = (
            request.configurable.thread_id if request.configurable else "unknown"
        )
        print(f"Error setting up stream run for thread {log_thread_id}: {e}")
        traceback.print_exc()
        # Consider returning a more informative error response if possible
        raise HTTPException(
            status_code=500, detail=f"Internal server error during stream setup: {e}"
        )

    # --- Compare Functionality Removed ---
    except HTTPException:
        raise
    except Exception as e:
        # Use thread_id from original request if available for logging
        log_thread_id = (
            request.configurable.thread_id if request.configurable else "unknown"
        )
        print(f"Error setting up stream run for thread {log_thread_id}: {e}")
        traceback.print_exc()
        # Consider returning a more informative error response if possible
        raise HTTPException(
            status_code=500, detail=f"Internal server error during stream setup: {e}"
        )


# --- Compare Functionality Removed ---

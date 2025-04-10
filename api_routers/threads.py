# src/api_routers/threads.py

import traceback
import json # Added missing import
import logging
from typing import List, Optional
import aiosqlite
from fastapi import APIRouter, HTTPException, Path as FastApiPath, Depends, Response, status
from langgraph.checkpoint.base import CheckpointTuple, BaseCheckpointSaver

# Import models (adjust path if necessary, assuming backend_models is accessible)
from backend_models import (
    HistoryEntry, MessageTypeModel, RunConfig,
    HumanApiMessageModel, AiApiMessageModel, ToolApiMessageModel, SystemApiMessageModel
)
# Import Langchain message types for adaptation logic
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
# Import StateSnapshot and Any for type hinting
from langgraph.pregel import StateSnapshot # Try importing from pregel
from typing import List, Optional, Any

# Dependency function to get the checkpointer (will be passed during router inclusion)
# This is a placeholder; the actual checkpointer comes from the main app instance.
# We'll rely on it being passed correctly rather than using Depends here directly.
# def get_checkpointer() -> BaseCheckpointSaver:
#     # In a real scenario, this might fetch from app state or context
#     # For now, we assume it's passed correctly when including the router
#     if not router.checkpointer_instance:
#          raise HTTPException(status_code=500, detail="Checkpointer not configured for thread router.")
#     return router.checkpointer_instance

# Create the router instance
router = APIRouter(
    prefix="/api/threads",
    tags=["threads"]
)
# Add attributes to hold instances passed from the main app
router.checkpointer_instances = None
router.graph_app_instance = None # Add attribute for graph instance

# --- Helper Function to Adapt StateSnapshot to HistoryEntry ---
def _adapt_snapshot_to_history_entry(
    state_snapshot: StateSnapshot, default_thread_id: str
) -> Optional[HistoryEntry]:
    """Converts a StateSnapshot to the HistoryEntry structure."""
    if not state_snapshot or not state_snapshot.values or not state_snapshot.config:
        print("Warning: Invalid StateSnapshot received.")
        return None

    config = state_snapshot.config
    values = state_snapshot.values
    metadata = state_snapshot.metadata # Get metadata

    # Extract required fields from config
    checkpoint_id = config.get("configurable", {}).get("checkpoint_id")
    if not checkpoint_id:
         # Attempt to get from snapshot metadata if available (structure might vary)
         # For now, raise error if not in config as expected by frontend
         raise ValueError("checkpoint_id missing in state_snapshot.config['configurable']")

    thread_id = config.get("configurable", {}).get("thread_id", default_thread_id)

    # Extract RunConfig from the configurable field stored in the snapshot's config
    run_config_dict = config.get("configurable", {}).get("runConfig")
    try:
        run_config_obj = RunConfig.model_validate(run_config_dict) if run_config_dict else RunConfig(configuredModules=[])
    except Exception as e:
        print(f"Warning: Could not parse runConfig from snapshot config {checkpoint_id} for thread {thread_id}: {e}")
        run_config_obj = RunConfig(configuredModules=[]) # Default to empty on parse error

    # Extract messages directly from state snapshot values
    raw_messages = values.get("messages", [])
    if not isinstance(raw_messages, list):
         print(f"Warning: 'messages' in snapshot values is not a list for thread {thread_id}. Found: {type(raw_messages)}")
         raw_messages = []

    adapted_messages: List[MessageTypeModel] = []
    for i, msg in enumerate(raw_messages):
        msg_data = {}
        adapted_msg = None
        msg_name = getattr(msg, 'name', None)
        msg_type = getattr(msg, 'type', None)
        node_id = msg_name # Use msg.name directly as the source

        # Explicitly set nodeId for HumanMessages
        if msg_type == 'human':
            node_id = 'user'

        # --- Adapt based on type ---
        # Let Pydantic validation handle missing nodeId loudly if required by the specific model
        if msg_type == 'human':
            msg_data = {
                "type": "human",
                "content": str(msg.content),
                "name": msg_name,
                "tool_call_id": None,
                "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                "nodeId": node_id
            }
            adapted_msg = HumanApiMessageModel.model_validate(msg_data)
        elif msg_type == 'ai':
            extracted_content: Optional[str] = None
            raw_content = msg.content
            if isinstance(raw_content, list):
                for part in raw_content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        extracted_content = part.get("text")
                        break
            elif isinstance(raw_content, str):
                extracted_content = raw_content
            else:
                extracted_content = str(raw_content)

            tool_calls = getattr(msg, 'tool_calls', [])
            if not isinstance(tool_calls, list): tool_calls = []

            invalid_tool_calls = getattr(msg, 'invalid_tool_calls', [])
            if not isinstance(invalid_tool_calls, list): invalid_tool_calls = []

            msg_data = {
                "type": "ai",
                "content": extracted_content,
                "name": msg_name,
                "tool_call_id": None,
                "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                "tool_calls": tool_calls,
                "invalid_tool_calls": invalid_tool_calls,
                "nodeId": node_id
            }
            adapted_msg = AiApiMessageModel.model_validate(msg_data)
        elif msg_type == 'tool':
             msg_data = {
                "type": "tool",
                "content": str(msg.content),
                "name": msg_name,
                "tool_call_id": str(getattr(msg, 'tool_call_id', f'missing_id_{i}')),
                "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                "is_error": isinstance(msg.content, Exception),
                "nodeId": node_id
            }
             adapted_msg = ToolApiMessageModel.model_validate(msg_data)
        elif msg_type == 'system':
             msg_data = {
                "type": "system",
                "content": str(msg.content),
                "name": msg_name,
                "tool_call_id": None,
                "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                "nodeId": node_id
            }
             adapted_msg = SystemApiMessageModel.model_validate(msg_data)
        else:
             # Handle potential other message types if necessary, or raise error
             print(f"Warning: Unhandled message type '{msg_type}' at index {i} for thread {thread_id}")
             continue # Skip unhandled types for now

        if adapted_msg:
            adapted_messages.append(adapted_msg)
        # Pydantic validation errors will propagate

    return HistoryEntry(
        checkpoint_id=str(checkpoint_id),
        thread_id=str(thread_id),
        values={"messages": adapted_messages},
        runConfig=run_config_obj
    )


@router.get("/{thread_id}/latest", response_model=HistoryEntry)
async def get_thread_latest_endpoint(
    thread_id: str = FastApiPath(..., title="The checkpoint thread ID (UUID string)")
):
    """Retrieves the latest history entry (snapshot state) for a specific thread ID."""
    graph_app = router.graph_app_instance # Access passed graph instance
    if not graph_app:
        print("Error: Graph app not available for getting latest state.")
        raise HTTPException(status_code=500, detail="Graph application service unavailable.")

    try:
        print(f"Fetching latest state snapshot for Thread ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        # Use graph.aget_state to get the StateSnapshot
        state_snapshot: Optional[StateSnapshot] = await graph_app.aget_state(config)

        if not state_snapshot:
            # Check if the thread exists at all using the checkpointer
            checkpointer = router.checkpointer_instance
            if checkpointer:
                 cp_tuple = await checkpointer.aget_tuple(config)
                 if not cp_tuple:
                      raise HTTPException(status_code=404, detail=f"No history found for thread ID: {thread_id}")
            # If thread exists but state is None, it's an unexpected issue
            print(f"Warning: Thread {thread_id} exists but aget_state returned None.")
            raise HTTPException(status_code=404, detail=f"Could not retrieve latest state for thread ID: {thread_id}")


        # Adapt the StateSnapshot using the new helper function
        history_entry = _adapt_snapshot_to_history_entry(state_snapshot, thread_id)

        if not history_entry:
             # This indicates an issue within the adaptation function itself
             print(f"Error: Failed to adapt state snapshot to HistoryEntry for thread {thread_id}")
             raise HTTPException(status_code=500, detail="Failed to process history data.")

        return history_entry

    except HTTPException:
        raise # Re-raise specific HTTP errors (like 404)
    except Exception as e:
        print(f"Error getting latest history for thread {thread_id}: {e}")
        traceback.print_exc()
        # Catch potential ValidationErrors from adaptation and return 500
        raise HTTPException(status_code=500, detail=f"Failed to load latest history: {e}")


@router.get("/{thread_id}/history", response_model=List[HistoryEntry])
async def get_thread_history_endpoint(
    thread_id: str = FastApiPath(..., title="The checkpoint thread ID (UUID string)")
):
    """Retrieves all history entries (snapshot states) for a specific thread ID."""
    graph_app = router.graph_app_instance # Access passed graph instance
    if not graph_app:
        print("Error: Graph app not available for getting history.")
        raise HTTPException(status_code=500, detail="Graph application service unavailable.")

    history_entries: List[HistoryEntry] = []
    try:
        print(f"Fetching state history for Thread ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        snapshot_count = 0
        # Use graph.aget_state_history to iterate through snapshots
        async for state_snapshot in graph_app.aget_state_history(config):
            snapshot_count += 1
            entry = _adapt_snapshot_to_history_entry(state_snapshot, thread_id)
            if entry:
                history_entries.append(entry)
            else:
                cp_id = state_snapshot.config.get("configurable", {}).get("checkpoint_id", "unknown")
                print(f"Warning: Failed to adapt state snapshot {cp_id} for thread {thread_id}")

        if snapshot_count == 0:
             # Check if the thread exists at all using the checkpointer
             checkpointer = router.checkpointer_instance
             if checkpointer:
                  cp_tuple = await checkpointer.aget_tuple(config)
                  if not cp_tuple:
                       print(f"No history found for thread_id: {thread_id}")
                       # Return empty list, not 404, as per original logic
                       return []
             # If thread exists but no snapshots, return empty list
             print(f"Thread {thread_id} exists but aget_state_history yielded no snapshots.")
             return []


        # Return the list of HistoryEntry objects
        # Note: aget_state_history iterates oldest to newest, which matches frontend expectation
        return history_entries

    except HTTPException:
        raise # Re-raise specific HTTP errors
    except Exception as e:
        print(f"Error getting history for thread {thread_id}: {e}")
        traceback.print_exc()
        # Catch potential ValidationErrors from adaptation and return 500
        raise HTTPException(status_code=500, detail=f"Failed to load history: {e}")


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread_endpoint(
    thread_id: str = FastApiPath(..., title="The LangGraph thread ID (UUID string) to delete")
):
    """Deletes all checkpoint data associated with a specific thread ID."""
    checkpointer = router.checkpointer_instance # Access passed checkpointer
    if not checkpointer:
        print("Error: Checkpointer not available for deleting thread.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    # Need AsyncSqliteSaver for direct deletion
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    if not isinstance(checkpointer, AsyncSqliteSaver):
        print(f"Error: Checkpointer is not an AsyncSqliteSaver ({type(checkpointer)}), cannot delete thread directly.")
        raise HTTPException(status_code=501, detail="Deletion not supported for this checkpointer type.")

    print(f"Attempting to delete thread ID: {thread_id}")
    try:
        # Use the checkpointer's connection for deletion
        async with checkpointer.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} rows from checkpoints table for thread {thread_id}")
            # Consider deleting from 'writes' table if it exists and is relevant
            # await cursor.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))

        await checkpointer.conn.commit()
        print(f"Successfully deleted data for thread ID: {thread_id}")

        if deleted_count == 0:
            print(f"Warning: No checkpoint data found for thread ID '{thread_id}' during deletion.")

        # Return 204 No Content on success
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except aiosqlite.Error as db_err:
        print(f"Database error deleting thread {thread_id}: {db_err}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error deleting thread: {db_err}")
    except Exception as e:
        print(f"Unexpected error deleting thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error deleting thread: {e}")

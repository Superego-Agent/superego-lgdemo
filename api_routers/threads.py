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
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

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
# Add an attribute to hold the checkpointer instance passed from the main app
router.checkpointer_instance: Optional[BaseCheckpointSaver] = None

# --- Helper Function to Adapt Checkpoint to HistoryEntry ---
# Moved from backend_server_async.py
def _adapt_checkpoint_to_history_entry(
    checkpoint_tuple: CheckpointTuple, default_thread_id: str
) -> Optional[HistoryEntry]:
    """Converts a CheckpointTuple to the HistoryEntry structure."""
    if not checkpoint_tuple or not checkpoint_tuple.checkpoint:
        return None

    checkpoint = checkpoint_tuple.checkpoint
    config = checkpoint_tuple.config

    # Extract required fields
    checkpoint_id = config.get("configurable", {}).get("checkpoint_id") or checkpoint.get("id") # Prefer ID from config if available, fallback to checkpoint's own ID
    thread_id = config.get("configurable", {}).get("thread_id", default_thread_id)

    # Extract RunConfig from the configurable field stored in the checkpoint
    run_config_dict = config.get("configurable", {}).get("runConfig")
    run_config_obj = None
    if run_config_dict:
        try:
            run_config_obj = RunConfig.model_validate(run_config_dict)
        except Exception as e:
            print(f"Warning: Could not parse runConfig from checkpoint {checkpoint_id} for thread {thread_id}: {e}")
            run_config_obj = RunConfig(configuredModules=[])
    else:
        print(f"Warning: runConfig not found in checkpoint {checkpoint_id} for thread {thread_id}. Using empty default.")
        run_config_obj = RunConfig(configuredModules=[])

    # Extract messages (raw format)
    raw_messages = checkpoint.get("channel_values", {}).get("messages", [])

    # Adapt messages
    adapted_messages: List[MessageTypeModel] = []
    for i, msg in enumerate(raw_messages):
        msg_data = {}
        adapted_msg = None
        try:
            if isinstance(msg, HumanMessage):
                # Extract nodeId - Raise error if missing
                node_id = None
                if isinstance(msg.additional_kwargs, dict):
                    node_id = msg.additional_kwargs.get('metadata', {}).get('node_id')
                    if not node_id:
                         node_id = msg.additional_kwargs.get('node_id') # Check directly under additional_kwargs

                if not node_id:
                    # If still not found, raise an error as it's required
                    raise ValueError(f"Could not determine required nodeId for message {i} (type: HumanMessage)")

                msg_data = {
                    "type": "human",
                    "content": str(msg.content),
                    "name": getattr(msg, 'name', None),
                    "tool_call_id": None, # Human messages don't have tool_call_id
                    "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                    "nodeId": node_id
                }
                adapted_msg = HumanApiMessageModel.model_validate(msg_data)
            elif isinstance(msg, AIMessage):
                # Handle content potentially being a list (e.g., tool calls)
                content_str = str(msg.content) if not isinstance(msg.content, list) else json.dumps(msg.content)
                # Extract tool calls safely
                # Properly extract text content and tool calls
                extracted_content: Optional[str] = None
                raw_content = msg.content

                if isinstance(raw_content, list):
                    # Find the first text part for content
                    for part in raw_content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            extracted_content = part.get("text")
                            break
                    # If no text part found, content remains None (as AiApiMessageModel.content is Optional)
                elif isinstance(raw_content, str):
                    extracted_content = raw_content
                else:
                    # Fallback for unexpected content types
                    extracted_content = str(raw_content)

                # Extract tool calls safely, ensuring it's a list
                tool_calls = getattr(msg, 'tool_calls', [])
                if not isinstance(tool_calls, list): tool_calls = [] # Ensure list type

                invalid_tool_calls = getattr(msg, 'invalid_tool_calls', [])
                if not isinstance(invalid_tool_calls, list): invalid_tool_calls = [] # Ensure list type

                # Attempt to extract nodeId from metadata if available
                node_id = msg.additional_kwargs.get('metadata', {}).get('node_id') if isinstance(msg.additional_kwargs, dict) else None
                msg_data = {
                    "type": "ai",
                    "content": extracted_content, # Use the extracted text content (can be None)
                    "name": getattr(msg, 'name', None),
                    "tool_call_id": None, # AI messages don't have a single tool_call_id
                    "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                    "tool_calls": tool_calls, # Assign the extracted tool calls list
                    "invalid_tool_calls": invalid_tool_calls, # Assign the extracted invalid tool calls list
                    "nodeId": node_id # Add nodeId
                }
                adapted_msg = AiApiMessageModel.model_validate(msg_data)
            elif isinstance(msg, ToolMessage):
                # Attempt to extract nodeId from metadata if available
                node_id = msg.additional_kwargs.get('metadata', {}).get('node_id') if isinstance(msg.additional_kwargs, dict) else None
                msg_data = {
                    "type": "tool",
                    "content": str(msg.content),
                    "name": getattr(msg, 'name', None),
                    "tool_call_id": str(getattr(msg, 'tool_call_id', f'missing_id_{i}')),
                    "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                    "is_error": isinstance(msg.content, Exception), # Check if content is an Exception
                    "nodeId": node_id # Add nodeId
                }
                adapted_msg = ToolApiMessageModel.model_validate(msg_data)
            else: # Treat as SystemMessage or fallback
                # Attempt to extract nodeId from metadata if available
                node_id = msg.additional_kwargs.get('metadata', {}).get('node_id') if isinstance(msg.additional_kwargs, dict) else None
                msg_data = {
                    "type": "system",
                    "content": str(msg.content),
                    "name": getattr(msg, 'name', None),
                    "tool_call_id": None,
                    "additional_kwargs": getattr(msg, 'additional_kwargs', None),
                    "nodeId": node_id # Add nodeId
                }
                adapted_msg = SystemApiMessageModel.model_validate(msg_data)

            if adapted_msg:
                adapted_messages.append(adapted_msg)

        except Exception as e:
            # Log the specific data that failed validation for this type
            print(f"Warning: Failed to adapt message {i} (type: {type(msg).__name__}) for thread {thread_id}: {e}. Data attempted: {msg_data}")

    return HistoryEntry(
        checkpoint_id=str(checkpoint_id) if checkpoint_id else "unknown",
        thread_id=str(thread_id),
        values={"messages": adapted_messages},
        runConfig=run_config_obj
    )


@router.get("/{thread_id}/latest", response_model=HistoryEntry)
async def get_thread_latest_endpoint(
    thread_id: str = FastApiPath(..., title="The checkpoint thread ID (UUID string)")
    # checkpointer: BaseCheckpointSaver = Depends(get_checkpointer) # Use dependency injection later if needed
):
    """Retrieves the latest history entry (checkpoint state) for a specific thread ID."""
    checkpointer = router.checkpointer_instance # Access passed checkpointer
    if not checkpointer:
        print("Error: Checkpointer not available for getting latest state.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    try:
        print(f"Fetching latest checkpoint for Thread ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple: Optional[CheckpointTuple] = await checkpointer.aget_tuple(config)

        if not checkpoint_tuple:
            raise HTTPException(status_code=404, detail=f"No history found for thread ID: {thread_id}")

        history_entry = _adapt_checkpoint_to_history_entry(checkpoint_tuple, thread_id)

        if not history_entry:
             print(f"Error: Failed to adapt checkpoint to HistoryEntry for thread {thread_id}")
             raise HTTPException(status_code=500, detail="Failed to process history data.")

        return history_entry

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting latest history for thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load latest history.")


# TODO: Fix this endpoint logic after file splitting is complete
@router.get("/{thread_id}/history", response_model=List[HistoryEntry]) # Changed response model
async def get_thread_history_endpoint(
    thread_id: str = FastApiPath(..., title="The checkpoint thread ID (UUID string)")
    # checkpointer: BaseCheckpointSaver = Depends(get_checkpointer)
):
    """Retrieves all history entries (checkpoint states) for a specific thread ID."""
    checkpointer = router.checkpointer_instance # Access passed checkpointer
    if not checkpointer:
        print("Error: Checkpointer not available for getting history.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    try:
        # Directly use the provided string thread_id with the checkpointer
        print(f"Fetching all checkpoints for Thread ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        # Fetch all checkpoint tuples for the thread using alist
        checkpoint_tuples: List[CheckpointTuple] = await checkpointer.alist(config)

        if not checkpoint_tuples:
             print(f"No checkpoints found for thread_id: {thread_id}")
             # Return an empty list if no history exists
             return []

        # Adapt each checkpoint tuple to the HistoryEntry structure
        history_entries: List[HistoryEntry] = []
        for cp_tuple in checkpoint_tuples:
            entry = _adapt_checkpoint_to_history_entry(cp_tuple, thread_id)
            if entry:
                history_entries.append(entry)
            else:
                # Log if a specific checkpoint failed adaptation
                cp_id = cp_tuple.config.get("configurable", {}).get("checkpoint_id") or cp_tuple.checkpoint.get("id")
                print(f"Warning: Failed to adapt checkpoint {cp_id} for thread {thread_id}")

        # Return the list of HistoryEntry objects, implicitly sorted by the checkpointer
        return history_entries

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
        print(f"Error getting history for thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load history.")


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread_endpoint(
    thread_id: str = FastApiPath(..., title="The LangGraph thread ID (UUID string) to delete")
    # checkpointer: BaseCheckpointSaver = Depends(get_checkpointer)
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
        async with checkpointer.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} rows from checkpoints table for thread {thread_id}")
            # Add deletion for 'writes' table if necessary
            # await cursor.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))

        await checkpointer.conn.commit()
        print(f"Successfully deleted data for thread ID: {thread_id}")

        if deleted_count == 0:
            print(f"Warning: No checkpoint data found for thread ID '{thread_id}' during deletion.")

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except aiosqlite.Error as e:
        print(f"Database error deleting thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database error deleting thread: {e}")
    except Exception as e:
        print(f"Unexpected error deleting thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error deleting thread: {e}")

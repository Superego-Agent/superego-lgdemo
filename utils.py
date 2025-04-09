import functools
import sys
import traceback
from typing import Callable, Any
import json
from typing import Literal, Optional, Any
from sse_starlette.sse import ServerSentEvent
from pydantic import ValidationError
from backend_models import SSEEventData, SSERunStartData, SSEToolCallChunkData, SSEToolResultData, SSEEndData

# Define the full Literal type for SSE events here for the helper function
SSEEventType = Literal["run_start", "chunk", "ai_tool_chunk", "tool_result", "error", "end"]



try:
    from rich.console import Console
    error_console = Console(stderr=True, style="bold red")
    def _print_error(func_name: str, e: Exception):
        error_console.print(f"\n>>> FAILED AT: {func_name} <<<")
        error_console.print(f"    Error: {e.__class__.__name__}: {e}")
        # traceback.print_exc()
except ImportError:
    def _print_error(func_name: str, e: Exception):
        print(f"\n>>> FAILED AT: {func_name} <<<", file=sys.stderr)
        print(f"    Error: {e.__class__.__name__}: {e}", file=sys.stderr)
        # traceback.print_exc()

def shout_if_fails(func: Callable) -> Callable:
    """
    Decorator: Executes function, prints clean error & re-raises on exception.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _print_error(func.__name__, e)
            raise 
    return wrapper


# --- SSE Event Helper Function ---
async def prepare_sse_event(
    event_type: SSEEventType,
    # Removed node and set_id parameters, node is now expected within data_payload
    data_payload: Any,
    thread_id: Optional[str]
) -> ServerSentEvent:
    """
    Safely creates a ServerSentEvent payload and object.
    Returns the intended event or a fallback error event if creation fails.
    Logs success/failure during preparation.
    """
    log_prefix = f"[SSE Prep - {event_type} - Thread: {thread_id or 'N/A'}]"
    try:
        # Validate data payload if it's a Pydantic model expected by SSEEventData
        # This helps catch errors before SSEEventData creation itself
        if isinstance(data_payload, (SSERunStartData, SSEToolCallChunkData, SSEToolResultData, SSEEndData)):
             # Re-validate to ensure consistency, though it should be valid if constructed correctly
             data_payload.model_validate(data_payload.model_dump()) # Or just pass through if already validated

        # Node and set_id are no longer top-level fields in SSEEventData
        sse_data = SSEEventData(
            type=event_type,
            data=data_payload,
            thread_id=thread_id
        )
        print(f"{log_prefix} Payload prepared successfully.")
        return ServerSentEvent(data=sse_data.model_dump_json())
    except (ValidationError, Exception) as e:
        error_msg = f"Error preparing SSE event payload: {e}"
        print(f"{log_prefix} {error_msg}")
        # Don't print full traceback here unless debugging, keep log cleaner
        # traceback.print_exc()

        # Create a fallback error event payload
        try:
            # Try to extract node from original payload for fallback error, default otherwise
            fallback_node = getattr(data_payload, 'node', 'event_preparation') if hasattr(data_payload, 'node') else 'event_preparation'
            # Create fallback error data payload (assuming SSEErrorData model exists)
            # If SSEErrorData doesn't exist or causes issues, revert to simple string
            try:
                from backend_models import SSEErrorData # Local import to avoid circular dependency if utils is imported by models
                fallback_data = SSEErrorData(node=fallback_node, error=error_msg)
            except ImportError:
                 # Fallback if SSEErrorData isn't defined or import fails
                 fallback_data = {"node": fallback_node, "error": error_msg} # Simple dict

            error_sse_data = SSEEventData(
                type="error",
                data=fallback_data,
                thread_id=thread_id
            )
            print(f"{log_prefix} Returning fallback error event.")
            return ServerSentEvent(data=error_sse_data.model_dump_json())
        except Exception as fallback_e:
            # If even the error event fails, log critical failure
            critical_error_msg = f"CRITICAL: Failed to create even fallback error SSE event: {fallback_e}"
            print(f"{log_prefix} {critical_error_msg}")
            # Return a raw text error event as last resort
            return ServerSentEvent(data=json.dumps({"type": "error", "node": "critical", "data": critical_error_msg, "thread_id": thread_id}), event="error")

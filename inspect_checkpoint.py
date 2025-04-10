import pickle
import json
from typing import Any, Set, Dict, List, Tuple
# from langgraph.graph.message import AnyMessage # Don't use AnyMessage with isinstance
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage # Import concrete types
# Import your specific State class if available/needed for type checks

# --- Configuration ---
# Assume 'graph' is your compiled LangGraph (e.g., StateGraph) with a checkpointer
# Assume 'config' is your RunnableConfig, e.g., {"configurable": {"thread_id": "your_thread_id"}}
# --- End Configuration ---

def inspect_recursive(obj: Any, path: str = "root", visited: Set[int] = None, max_depth=15):
    """Recursively inspects an object and prints paths to values."""
    if visited is None:
        visited = set()

    if max_depth <= 0:
        print(f"{path}: <Max Recursion Depth Reached>")
        return

    # Handle None explicitly
    if obj is None:
        print(f"{path}: None")
        return

    obj_id = id(obj)
    if obj_id in visited and not isinstance(obj, (str, int, float, bool, bytes)):
        # Only stop recursion for container/complex types already visited
        # Allow primitives to be printed multiple times if they appear in different places
        print(f"{path}: <Circular Reference detected to object id {obj_id}, type {type(obj).__name__}>")
        return
    visited.add(obj_id)

    # --- Primitive Types ---
    if isinstance(obj, (str, int, float, bool, bytes)):
        print(f"{path}: {repr(obj)}")

    # --- Common Collections ---
    elif isinstance(obj, dict):
        prefix = f"{type(obj).__name__}(" if type(obj) != dict else ""
        suffix = ")" if type(obj) != dict else ""
        if not obj:
            print(f"{path}: {prefix}{{}}{suffix}")
        else:
            print(f"{path}: <{type(obj).__name__} with {len(obj)} items>")
            for key, value in obj.items():
                new_path = f"{path}[{repr(key)}]"
                inspect_recursive(value, new_path, visited.copy(), max_depth - 1)
    elif isinstance(obj, (list, tuple, set)):
        type_name = type(obj).__name__
        open_bracket = "[" if isinstance(obj, list) else "(" if isinstance(obj, tuple) else "{"
        close_bracket = "]" if isinstance(obj, list) else ")" if isinstance(obj, tuple) else "}"
        if not obj:
             print(f"{path}: {type_name}({open_bracket}{close_bracket})")
        else:
            print(f"{path}: <{type_name} with {len(obj)} items>")
            for index, item in enumerate(obj):
                # Use index for list/tuple, indicate unordered for set
                idx_repr = index if isinstance(obj, (list, tuple)) else f"item_{index}"
                new_path = f"{path}[{idx_repr}]"
                inspect_recursive(item, new_path, visited.copy(), max_depth - 1)

    # --- LangChain/Graph Specific Objects (Add more as needed) ---
    # Check against a tuple of concrete message types
    elif isinstance(obj, (HumanMessage, AIMessage, SystemMessage, ToolMessage)):
         print(f"{path}: <{type(obj).__name__}>")
         # Explicitly inspect common message attributes
         common_attrs = ['content', 'additional_kwargs', 'response_metadata', 'id', 'name', 'tool_calls', 'invalid_tool_calls', 'type', 'usage_metadata']
         for attr in common_attrs:
             if hasattr(obj, attr):
                 inspect_recursive(getattr(obj, attr), f"{path}.{attr}", visited.copy(), max_depth - 1)
         # Optionally inspect __dict__ for anything else, avoiding common attrs already checked
         if hasattr(obj, '__dict__'):
             for attr_name, attr_value in vars(obj).items():
                  if attr_name not in common_attrs and not attr_name.startswith('_'): # Avoid private/internal usually
                      if not callable(attr_value):
                          inspect_recursive(attr_value, f"{path}.{attr_name}", visited.copy(), max_depth-1)

    # --- General Objects ---
    else:
        # Check for __dict__ (most standard objects)
        if hasattr(obj, '__dict__'):
            print(f"{path}: <Object of type {type(obj).__name__}>")
            if not vars(obj):
                 print(f"{path}.__dict__: {{}}")
            else:
                for attr_name, attr_value in vars(obj).items():
                    # Avoid inspecting methods, private/protected attributes usually
                    if not callable(attr_value) and not attr_name.startswith('_'):
                        new_path = f"{path}.{attr_name}"
                        inspect_recursive(attr_value, new_path, visited.copy(), max_depth - 1)
        # Check for __slots__ (more memory efficient objects)
        elif hasattr(obj, '__slots__'):
             print(f"{path}: <Object of type {type(obj).__name__} with __slots__>")
             for slot_name in obj.__slots__:
                 try:
                     slot_value = getattr(obj, slot_name)
                     if not callable(slot_value):
                        new_path = f"{path}.{slot_name}"
                        inspect_recursive(slot_value, new_path, visited.copy(), max_depth-1)
                 except AttributeError:
                     print(f"{path}.{slot_name}: <AttributeError accessing slot>")
        # Fallback for objects without obvious iteration or attributes
        else:
            print(f"{path}: <Unhandled Type: {type(obj).__name__} - Value: {repr(obj)}>")

# --- Main Execution Logic ---
if __name__ == "__main__":
    # Placeholder: You need to define 'graph' and 'config' here based on your setup
    # Example:
    # from langgraph.checkpoint.memory import MemorySaver
    # from langgraph.graph import StateGraph
    # graph = StateGraph(...) # Define your graph
    # graph.add_node(...)
    # graph.add_edge(...)
    # checkpointer = MemorySaver()
    # graph = graph.compile(checkpointer=checkpointer)
    # config = {"configurable": {"thread_id": "some-thread-id-123"}}
    # # Make sure the thread exists by running the graph at least once
    # # graph.invoke({"messages": [("user", "hello")]}, config=config)

    # --- ACTUAL CONFIGURATION FOR THIS PROJECT ---
    import asyncio
    # Import necessary functions from superego_core_async and models
    from superego_core_async import create_models, create_workflow
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver # Correct import path

    # Replicate the setup from backend_server_async.py lifespan
    async def initialize_graph_and_checkpointer():
        print("Initializing models and workflow for inspection...")
        superego_model, inner_model = create_models()
        # create_workflow should return the compiled graph and the checkpointer instance
        graph_app, checkpointer_instance, _ = await create_workflow(
            superego_model=superego_model,
            inner_model=inner_model
        )
        print("Initialization complete.")
        return graph_app, checkpointer_instance

    # Define the config for the thread you want to inspect
    # Replace 'your_thread_id_here' with an actual thread ID from your conversations.db
    thread_id_to_inspect = "16f7f116-fbda-4eb5-96f1-6edf232aef18" # <<< --- !!! USER: REPLACE THIS !!!
    config = {"configurable": {"thread_id": thread_id_to_inspect}}
    # --- END ACTUAL CONFIGURATION ---

    # --- Main Async Function ---
    async def main():
        # Initialize graph and checkpointer
        graph, checkpointer = await initialize_graph_and_checkpointer()

        if graph is None or checkpointer is None or config is None or thread_id_to_inspect == "your_thread_id_here":
            print("Error: Please define 'graph', 'checkpointer', and 'config' in the script.")
            print("       Specifically, replace 'your_thread_id_here' with a valid thread ID.")
            # Add a check if initialization failed
            if graph is None or checkpointer is None:
                 print("       Initialization of graph or checkpointer failed.")
            return # Exit if initialization failed or config is incomplete

        print(f"Inspecting checkpoint for config: {config}")
        print("-" * 40)
        try:
            # 1. Inspect the raw CheckpointTuple (might contain more metadata)
            print("\n--- Inspecting Raw Checkpoint Tuple ---")
            # Use the checkpointer instance directly
            checkpoint_tuple = await checkpointer.aget_tuple(config) # Use await for async method
            if checkpoint_tuple:
                inspect_recursive(checkpoint_tuple, path="checkpoint_tuple")
            else:
                print(f"Could not retrieve checkpoint tuple for thread_id '{thread_id_to_inspect}'. Check if the ID is correct and the thread exists.")

            # 2. Inspect the StateSnapshot (processed state)
            print("\n--- Inspecting Processed State Snapshot ---")
            # Ensure graph is not None before calling aget_state
            if graph:
                # Use the async version aget_state
                state_snapshot = await graph.aget_state(config) # Use await for async method
                if state_snapshot:
                    inspect_recursive(state_snapshot, path="state_snapshot")
                else:
                    print(f"Could not retrieve state snapshot for thread_id '{thread_id_to_inspect}'.")
            else:
                 print("Skipping state snapshot inspection because graph initialization failed.")

        except Exception as e:
            print(f"\nAn error occurred during inspection: {e}")
            import traceback
            traceback.print_exc()
        finally:
             # Attempt to close the checkpointer connection if it exists and has a close method
             if checkpointer and hasattr(checkpointer, 'aclose') and callable(checkpointer.aclose):
                 print("\nClosing checkpointer connection...")
                 try:
                     await checkpointer.aclose()
                     print("Checkpointer connection closed.")
                 except Exception as close_err:
                     print(f"Error closing checkpointer: {close_err}")
             elif checkpointer and hasattr(checkpointer, 'close') and callable(checkpointer.close):
                 # Fallback for synchronous close if aclose doesn't exist
                 print("\nClosing checkpointer connection (sync)...")
                 try:
                     checkpointer.close()
                     print("Checkpointer connection closed (sync).")
                 except Exception as close_err:
                     print(f"Error closing checkpointer (sync): {close_err}")

        print("-" * 40)

    # Run the main async function once
    asyncio.run(main())

import pickle
import json
from typing import Any, Set, Dict, List, Tuple
from langgraph.graph.message import AnyMessage  # Import message types if needed
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
    elif isinstance(obj, AnyMessage): # Base class for LangChain messages
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

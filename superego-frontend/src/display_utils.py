# display_utils.py
import json
from typing import List, Optional, Dict, Any, Union, Tuple
from dataclasses import dataclass, field
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.markup import escape
from rich.table import Table
from rich.console import Group # Still needed for _display_history in cli.py

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, AIMessageChunk

from cli_constants import STYLES, NODE_COLORS

class CliState: pass # Forward declaration

def print_as(console: Console, level: str, message: str):
    style = STYLES.get(level, STYLES["default"])
    prefix = f"{level.capitalize()}: " if level in ["error", "warning"] else ""
    console.print(f"[{style}]{prefix}{escape(message)}[/{style}]")

# --- Panel Creation (Used by history display in cli.py) ---
def create_panel_for_message(msg: BaseMessage) -> Optional[Panel]:
    if isinstance(msg, HumanMessage): return None
    elif isinstance(msg, (AIMessage, AIMessageChunk)):
        content_str = "";
        if isinstance(msg.content, str): content_str = msg.content
        elif isinstance(msg.content, list): content_str = "".join(i.get("text","") for i in msg.content if isinstance(i,dict) and i.get("type")=="text")
        node_name = getattr(msg, 'name', None)
        title = "AI Agent"; color = NODE_COLORS.get("inner_agent", NODE_COLORS["DEFAULT"])
        if node_name and node_name != "AI": title = node_name.replace("_", " ").title(); color = NODE_COLORS.get(node_name, NODE_COLORS["DEFAULT"])
        tool_calls = ""
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                 name = escape(tc.get('name', 'N/A'))
                 try: args = json.dumps(tc.get('args', {}))
                 except Exception: args = str(tc.get('args', {}))
                 tool_calls += f"\n[dim]-> Called {name} Tool: {escape(args)}[/dim]"
        full = escape(content_str.strip()) + tool_calls
        return Panel(full, title=f">>> {title}", border_style=color, expand=False) if full.strip() else None
    elif isinstance(msg, ToolMessage):
        content = escape(str(msg.content)) if msg.content is not None else "[dim](No content)[/dim]"
        name = escape(getattr(msg, 'name', 'Unknown Tool'))
        return Panel(content, title=f"<<< Tool Result ({name})", border_style=STYLES["tool_result"], expand=False)
    return None

# --- Streaming Display ---

def _find_tool_name(turn_messages: List[BaseMessage], tool_call_id: Optional[str]) -> str:
    """Search backwards in memory for the tool name matching the ID."""
    if not tool_call_id: return "? Tool"
    for msg in reversed(turn_messages):
        if isinstance(msg, AIMessageChunk) and msg.tool_call_chunks:
            for chunk in msg.tool_call_chunks:
                if chunk.get("id") == tool_call_id and chunk.get("name"):
                    return chunk["name"]
    return "? Tool" # Not found

def run_graph_and_display_live(
    console: Console,
    state: CliState,
    constitution_content_for_run: str,
    messages_to_send: List[BaseMessage],
    title_prefix: str = ""
):
    config = {"configurable": {"thread_id": state.thread_id, "constitution_content": constitution_content_for_run}}
    if title_prefix: print_as(console, "highlight", f"\n--- {title_prefix} ---")

    current_live: Optional[Live] = None
    current_panel: Optional[Panel] = None
    current_buffer: str = ""
    last_node: Optional[str] = None
    turn_messages: List[BaseMessage] = [] # In-memory cache for this turn's messages
    stream_finished = False

    try:
        stream_iterator = state.graph_app.stream({'messages': messages_to_send}, config=config, stream_mode="messages")
        for event in stream_iterator:
            stream_finished = True; chunk: Optional[BaseMessage] = None; metadata: Dict[str, Any] = {}
            if isinstance(event, tuple) and len(event) == 2 and isinstance(event[0], BaseMessage): chunk, metadata = event
            elif isinstance(event, BaseMessage): chunk = event; metadata = getattr(chunk, 'metadata', {}) or {}
            else: continue
            if not chunk: continue

            turn_messages.append(chunk) # Cache message
            current_node = metadata.get("langgraph_node") or getattr(chunk, 'name', None)
            if not current_node: continue

            is_new_node = (current_node != last_node)
            is_tool_result_chunk = isinstance(chunk, ToolMessage)
            is_ai_chunk = isinstance(chunk, AIMessageChunk)

            # --- Stop existing Live panel if node changes or tool result arrives ---
            if current_live and (is_new_node or is_tool_result_chunk):
                current_live.stop()
                current_live = None
                current_panel = None
                current_buffer = "" # Reset buffer

            # --- Handle Tool Result (Print Statically) ---
            if is_tool_result_chunk:
                tool_name = _find_tool_name(turn_messages, getattr(chunk, 'tool_call_id', None))
                content = escape(str(chunk.content)) if chunk.content is not None else "[dim](No content)[/dim]"
                panel = Panel(content, title=f"<<< Tool Result ({escape(tool_name)})", border_style=STYLES["tool_result"], expand=False)
                console.print(panel)
                last_node = current_node # Treat tool node as the last node processed
                continue # Handled tool result, move to next event

            # --- Handle AI Chunk (Streaming) ---
            if is_ai_chunk and (chunk.content or chunk.tool_call_chunks) and current_node != "tools":
                # Start new Live session if needed
                if current_live is None:
                    color = NODE_COLORS.get(current_node, NODE_COLORS["DEFAULT"])
                    title = f">>> {current_node.replace('_', ' ').title()}"
                    current_panel = Panel("", title=title, border_style=color, expand=False)
                    current_buffer = ""
                    current_live = Live(current_panel, console=console, auto_refresh=False, vertical_overflow="visible")
                    current_live.start(refresh=True)

                # Process Text
                text_content = "";
                if isinstance(chunk.content, str): text_content = chunk.content
                elif isinstance(chunk.content, list): text_content = "".join(i.get("text","") for i in chunk.content if isinstance(i,dict) and i.get("type")=="text")
                if text_content:
                    current_buffer += escape(text_content)

                # Process Tool Chunks (Simplified Append)
                tool_chunks = getattr(chunk, 'tool_call_chunks', [])
                for tc in tool_chunks:
                    tc_id, name, args = tc.get("id"), tc.get("name"), tc.get("args")
                    # If start of call (id and name)
                    if tc_id and name:
                        current_buffer += f"\n[dim]-> Called {escape(name)} Tool: [/dim]"
                        # If args also present in *this* chunk, append directly
                        if 'args' in tc and tc.get('args') is not None:
                             current_buffer += f"[dim]{escape(str(args))}[/dim]"
                    # If just args fragment
                    elif not name and 'args' in tc and tc.get('args') is not None:
                        current_buffer += f"[dim]{escape(str(args))}[/dim]" # Append raw fragment

                # Update the current panel and refresh Live
                if current_panel is not None and current_live is not None:
                     current_panel.renderable = current_buffer
                     current_live.update(current_panel, refresh=True) # Update takes renderable, not Group

                last_node = current_node

    # Ensure the final streaming panel is stopped correctly
    finally:
        if current_live:
            current_live.stop()

    if not stream_finished: print_as(console, "warning", "No response stream received.")
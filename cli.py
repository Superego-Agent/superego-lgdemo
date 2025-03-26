# cli.py
import sys
import json
import datetime
import uuid
import os
import traceback
import re # Import re for parsing compare command
from typing import List, Optional, Dict, Any, Union, Tuple

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from rich.console import Console, Group
from rich.panel import Panel
from rich.live import Live
from rich.markup import escape
from rich.table import Table
from utils import shout_if_fails # Import the decorator

# --- Core & Optional Component Imports ---
from superego_core import create_workflow, create_models
from config import CONFIG
# Import the manager and constants/helpers from the refactored files
from constitution_manager import constitution_manager, DISALLOWED_ID_CHARS
from constitution_cli import list_constitutions as display_constitutions_table # Use the correct function name

# --- Rich Console & Constants ---
console = Console()
NODE_COLORS = {"superego": "yellow", "inner_agent": "green", "tools": "magenta"}
DEFAULT_NODE_COLOR = "cyan"
USER_COLOR = "blue"
TOOL_RESULT_COLOR = "magenta"
CONSTITUTION_SEPARATOR = "+" # Use '+' to combine constitutions

# --- State for CLI ---
current_constitution_content: str = ""
current_constitution_ids: List[str] = ["none"] # Start with 'none'
compare_mode_active: bool = False
compare_constitution_sets: List[List[str]] = []

# --- Helper to create Rich Panels (for History) ---
# (No changes needed in _create_panel_for_message)
def _create_panel_for_message(msg: BaseMessage, node_name_override: Optional[str] = None) -> Optional[Panel]:
    if isinstance(msg, HumanMessage):
        return None # Handled separately

    elif isinstance(msg, (AIMessage, AIMessageChunk)):
        content_str = ""
        if isinstance(msg.content, str):
            content_str = msg.content
        elif isinstance(msg.content, list):
             for item in msg.content:
                 if isinstance(item, dict) and item.get("type") == "text":
                     content_str += item.get("text", "")

        node_name = node_name_override or getattr(msg, 'name', None)
        title_node_name = "AI Agent"
        color = NODE_COLORS.get("inner_agent", DEFAULT_NODE_COLOR)

        # Determine title and color based on message name or override
        if node_name and node_name != "AI": # Check if node_name is not None or "AI"
            title_node_name = node_name.replace("_", " ").title()
            color = NODE_COLORS.get(node_name, DEFAULT_NODE_COLOR)
        elif node_name_override:
            title_node_name = node_name_override.replace("_", " ").title()
            color = NODE_COLORS.get(node_name_override, DEFAULT_NODE_COLOR)

        # Format tool calls if present (for non-streaming history display)
        tool_calls_str = ""
        # Check specifically for AIMessage, not AIMessageChunk for complete tool calls
        if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tc in msg.tool_calls:
                 tool_name = escape(tc.get('name', 'N/A'))
                 try:
                     args_display = json.dumps(tc.get('args', {}))
                 except Exception:
                     args_display = str(tc.get('args', {})) # Fallback for non-serializable args
                 tool_calls_str += f"\n[dim]-> Called {tool_name} Tool: {escape(args_display)}[/dim]"

        full_content = escape(content_str.strip()) + tool_calls_str

        if full_content.strip():
            return Panel(full_content, title=f">>> {title_node_name}", border_style=color, expand=False)
        else:
            # Return None if there's no content to display, even if it's an AIMessage
            # This prevents empty panels from appearing (e.g., superego only calls tool)
            return None

    elif isinstance(msg, ToolMessage):
        content_display = escape(str(msg.content)) if msg.content is not None else "[dim](No content returned)[/dim]"
        tool_name_display = escape(getattr(msg, 'name', 'Unknown Tool'))
        return Panel(content_display, title=f"<<< Tool Result ({tool_name_display})", border_style=TOOL_RESULT_COLOR, expand=False)

    return None


# --- History Display ---
@shout_if_fails
def display_history(thread_id: str, graph_app):
    console.print("\n--- Chat History ---", style="bold blue")
    config = {"configurable": {"thread_id": thread_id}}
    # Ensure state and messages are handled gracefully if they don't exist
    state = graph_app.get_state(config)
    messages = state.values.get('messages', []) if state and hasattr(state, 'values') else []


    history_renderables = []
    if not messages:
        history_renderables.append("[dim]No messages found for this thread.[/dim]")
    else:
        for msg in messages:
            if isinstance(msg, HumanMessage):
                 history_renderables.append(f"[{USER_COLOR} bold]User:[/ {USER_COLOR} bold] {escape(msg.content)}")
            else:
                panel = _create_panel_for_message(msg)
                if panel:
                    history_renderables.append(panel)

    console.print(Group(*history_renderables))
    console.print("--------------------\n", style="bold blue")


# --- Constitution Loading Helper (New) ---
def _load_constitutions(ids_string: str) -> Tuple[str, List[str]]:
    """Loads and combines constitutions based on a '+' separated string."""
    global current_constitution_content, current_constitution_ids
    ids_to_load = [id.strip() for id in ids_string.split(CONSTITUTION_SEPARATOR) if id.strip()]
    if not ids_to_load:
        ids_to_load = ["none"] # Default to 'none' if empty string provided

    # Validate IDs before attempting to load
    valid_ids = True
    for id_val in ids_to_load:
        if id_val != "none" and not constitution_manager._is_valid_id(id_val):
            console.print(f"[red]Error: Invalid constitution ID '{id_val}'. Cannot contain: '{DISALLOWED_ID_CHARS}'[/red]")
            valid_ids = False
    if not valid_ids:
        # Revert to previous valid state or 'none'
        combined_content, loaded_ids = constitution_manager.get_combined_constitution_content(current_constitution_ids)
        # Update globals just in case they were somehow modified mid-error
        current_constitution_content = combined_content
        current_constitution_ids = loaded_ids
        console.print(f"[yellow]Reverting to previously used constitution(s): [cyan]{CONSTITUTION_SEPARATOR.join(current_constitution_ids)}[/cyan][/yellow]")
        return combined_content, current_constitution_ids

    # Proceed with loading valid IDs
    combined_content, loaded_ids = constitution_manager.get_combined_constitution_content(ids_to_load)

    if not loaded_ids and "none" not in ids_to_load: # If none could be loaded and 'none' wasn't requested
        console.print(f"[yellow]Warning: Could not load any specified constitutions: {ids_string}. Using 'none'.[/yellow]")
        combined_content, loaded_ids = constitution_manager.get_combined_constitution_content(["none"])
    elif not loaded_ids and "none" in ids_to_load: # If 'none' was requested but failed (shouldn't happen with default file)
        console.print(f"[red]Error: Failed to load even the 'none' constitution. Check constitution directory.[/red]")
        combined_content = "" # Ensure content is empty
        loaded_ids = ["none"] # Reflect attempt

    # Update global state
    current_constitution_content = combined_content
    current_constitution_ids = loaded_ids

    ids_str = CONSTITUTION_SEPARATOR.join(loaded_ids)
    console.print(f"Using constitution(s): [cyan]{ids_str}[/cyan]")
    if len(loaded_ids) < len(ids_to_load):
        missing_ids = set(ids_to_load) - set(loaded_ids)
        console.print(f"[yellow]Warning: Could not load: {', '.join(missing_ids)}[/yellow]")

    return current_constitution_content, current_constitution_ids


# --- Command Help Display (Updated) ---
def display_help_commands():
    help_text = (
        "[bold cyan]Available Commands:[/bold cyan]\n"
        "- [bold]/help[/bold]: Show this help message.\n"
        "- [bold]/history[/bold]: View past conversation turns.\n"
        "- [bold]/new[/bold]: Start a new chat thread.\n"
        "- [bold]/constitutions[/bold]: List available constitutions.\n"
        f"- [bold]/use ID[{CONSTITUTION_SEPARATOR}ID2...][/bold]: Use constitution(s) for subsequent prompts (e.g., /use default{CONSTITUTION_SEPARATOR}strict). Use '/use none' to clear.\n"
        f"- [bold]/compare [ID1[{CONSTITUTION_SEPARATOR}ID2], ID3, ...][/bold]: Compare constitution sets on the next prompt (e.g., /compare [default, default{CONSTITUTION_SEPARATOR}strict, minimal]).\n"
        "- [bold]/compare_off[/bold]: Turn off compare mode.\n"
        "- [bold]/quit[/bold] or [bold]/exit[/bold]: Exit the chat."
    )
    help_panel = Panel(help_text, border_style="cyan", expand=False, title="Commands")
    console.print(help_panel)

# --- Parse Compare String (New) ---
def parse_compare_sets(compare_string: str) -> Optional[List[List[str]]]:
    """Parses the string provided to /compare into a list of constitution ID lists."""
    compare_string = compare_string.strip()
    if not compare_string.startswith('[') or not compare_string.endswith(']'):
        console.print("[red]Invalid format for /compare. Use brackets: /compare [set1, set2+set3, ...][/red]")
        return None

    content = compare_string[1:-1].strip()
    if not content:
        return [] # Empty list is valid

    set_strings = [s.strip() for s in content.split(',')]
    parsed_sets = []
    for set_str in set_strings:
        if not set_str:
            console.print("[red]Invalid format: Empty set found in /compare list.[/red]")
            return None
        ids = [id.strip() for id in set_str.split(CONSTITUTION_SEPARATOR) if id.strip()]
        if not ids:
             console.print(f"[red]Invalid format: Set '{set_str}' contains no valid IDs.[/red]")
             return None
        # Validate IDs within the set
        valid_ids_in_set = True
        for id_val in ids:
             if id_val != "none" and not constitution_manager._is_valid_id(id_val):
                 console.print(f"[red]Invalid constitution ID '{id_val}' in set '{set_str}'. Cannot contain: '{DISALLOWED_ID_CHARS}'[/red]")
                 valid_ids_in_set = False
                 break # Stop checking this set
             # Check if constitution exists
             if id_val != "none" and constitution_manager.get_constitution_content(id_val) is None:
                 console.print(f"[red]Error: Constitution '{id_val}' in set '{set_str}' not found.[/red]")
                 valid_ids_in_set = False
                 break # Stop checking this set
        if not valid_ids_in_set:
            return None # Abort parsing if any set has invalid/missing IDs
        parsed_sets.append(ids)

    return parsed_sets

# --- Stream Processing Function (New/Refactored) ---
def _run_graph_and_display(graph_app, thread_id: str, constitution_content_for_run: str, messages_to_send: List[BaseMessage], title_prefix: str = ""):
    """Runs the graph for a given constitution and displays the streaming output."""
    # Use the correct key "constitution_content"
    config = {"configurable": {"thread_id": thread_id, "constitution_content": constitution_content_for_run}}
    stream_finished = False

    # Diagnostic print: Show which constitution content is being used for this run
    console.print(f"[dim]Running with constitution content (first 100 chars): {escape(constitution_content_for_run[:100])}...[/dim]")

    live_display_elements = []
    current_turn_node_outputs: Dict[int, str] = {}
    current_turn_panels: List[Panel] = []
    last_processed_node: Optional[str] = None
    pending_tool_names: Dict[str, str] = {}
    active_tool_call_name: Optional[str] = None
    started_tool_call_line: set[str] = set() # Track which tool calls have started rendering

    def process_args_fragment(args_fragment: Optional[str], tool_name: str, panel_idx: int) -> bool:
        """Handles appending args fragment to the correct panel."""
        nonlocal new_content_added # Allow modification of outer scope variable
        args_val_str = str(args_fragment) if args_fragment is not None else ""
        if not args_val_str: return False

        panel_exists = panel_idx >= 0 and panel_idx < len(current_turn_panels) and current_turn_panels[panel_idx].title.startswith(">>>")
        if not panel_exists:
            # Should not happen if name chunk arrived first, but handle defensively
            console.print(f"[yellow]Warning: Args fragment arrived but no valid panel exists for index {panel_idx}.[/yellow]")
            return False

        if tool_name not in started_tool_call_line:
            # This case handles if args arrive before or with the name chunk
            initial_line = f"\n[dim]-> Called {escape(tool_name)} Tool: {{{escape(args_val_str)}}}[/dim]"
            current_turn_node_outputs[panel_idx] += initial_line
            current_turn_panels[panel_idx].renderable = current_turn_node_outputs[panel_idx]
            started_tool_call_line.add(tool_name)
            new_content_added = True
        else:
            # Tool call already started, append args inside {}
            current_content = current_turn_node_outputs[panel_idx]
            # Find the *last* occurrence related to this specific tool name to handle multiple calls
            # This is tricky; simple rfind might target the wrong tool if names repeat.
            # A more robust approach might involve tracking indices per tool, but let's try rfind for now.
            # We need to find the pattern "Called tool_name Tool: {...}" specific to this tool_name
            tool_start_pattern = f"Called {escape(tool_name)} Tool: {{"
            last_tool_start_index = current_content.rfind(tool_start_pattern)

            if last_tool_start_index != -1:
                # Find the closing '}' after this specific tool call started
                insert_marker = "}[/dim]"
                last_marker_index = current_content.find(insert_marker, last_tool_start_index)

                if last_marker_index != -1:
                     insert_pos = last_marker_index
                     new_content = current_content[:insert_pos] + escape(args_val_str) + current_content[insert_pos:]
                     current_turn_node_outputs[panel_idx] = new_content
                     current_turn_panels[panel_idx].renderable = new_content # Corrected panel index
                     new_content_added = True
                else:
                    # Fallback if closing marker wasn't found after start (unexpected)
                     fallback_str = f"\n[dim]Args({tool_name}, append failed - no marker): '{escape(args_val_str)}'[/dim]"
                     current_turn_node_outputs[panel_idx] += fallback_str
                     current_turn_panels[panel_idx].renderable = current_turn_node_outputs[panel_idx]
                     new_content_added = True

            else:
                # Fallback if the tool start pattern wasn't found (unexpected)
                fallback_str = f"\n[dim]Args({tool_name}, append failed - no start): '{escape(args_val_str)}'[/dim]"
                current_turn_node_outputs[panel_idx] += fallback_str
                current_turn_panels[panel_idx].renderable = current_turn_node_outputs[panel_idx]
                new_content_added = True

        return new_content_added

    # --- Stream Processing ---
    # Use console.print directly for compare mode titles
    if title_prefix:
        console.print(f"\n--- {title_prefix} ---", style="bold yellow")

    with Live(Group(*live_display_elements), console=console, auto_refresh=False, vertical_overflow="visible") as live:
        # Crucially, use stream_mode="messages" to get individual message chunks
        stream_iterator = graph_app.stream({'messages': messages_to_send}, config=config, stream_mode="messages")

        for event in stream_iterator:
            stream_finished = True # Mark that we received at least one event
            chunk: Optional[BaseMessage] = None
            metadata: Dict[str, Any] = {}

            # Handle different event structures (tuples or single messages)
            if isinstance(event, tuple) and len(event) == 2:
                 # Expecting (BaseMessage, metadata dict)
                 if isinstance(event[0], BaseMessage) and isinstance(event[1], dict):
                     chunk, metadata = event
                 else: continue # Skip unexpected tuple format
            elif isinstance(event, BaseMessage):
                 chunk = event
                 metadata = getattr(chunk, 'metadata', {}) or getattr(event, '__dict__', {}).get('metadata', {})
            else: continue # Skip unexpected event types
            if not chunk: continue

            # Determine the node that produced the chunk
            current_node = metadata.get("langgraph_node") or getattr(chunk, 'name', None)
            if not current_node: continue # Skip if node cannot be determined

            new_content_added = False
            current_panel_index = len(current_turn_panels) - 1 # Index of the last panel

            try:
                is_new_node_invocation = (current_node != last_processed_node)

                if isinstance(chunk, AIMessageChunk):
                    has_text_content = bool(chunk.content)
                    has_tool_chunks = hasattr(chunk, 'tool_call_chunks') and bool(chunk.tool_call_chunks)

                    # Determine if a new panel is needed or if we append to the last one
                    panel_exists_or_needed = (has_text_content or has_tool_chunks) and current_node != "tools"
                    needs_new_panel = False
                    if panel_exists_or_needed:
                        # Need new panel if it's a new node, no panels exist, or last panel was a tool result
                        if is_new_node_invocation or current_panel_index < 0 or current_turn_panels[current_panel_index].title.startswith("<<< Tool Result"):
                             needs_new_panel = True

                    if needs_new_panel:
                        color = NODE_COLORS.get(current_node, DEFAULT_NODE_COLOR)
                        title = f">>> {current_node.replace('_', ' ').title()}"
                        new_panel = Panel("", title=title, border_style=color, expand=False)
                        current_turn_panels.append(new_panel)
                        current_panel_index = len(current_turn_panels) - 1 # Update index
                        current_turn_node_outputs[current_panel_index] = "" # Initialize content store
                        live_display_elements = current_turn_panels # Update list for Live

                    # Check if the *current* panel (which might be newly created) is an AI panel
                    panel_is_ai = current_panel_index >= 0 and current_turn_panels[current_panel_index].title.startswith(">>>")

                    # 1. Process Text Content
                    if has_text_content and panel_is_ai:
                        text_content = ""
                        if isinstance(chunk.content, str): text_content = chunk.content
                        elif isinstance(chunk.content, list):
                            for item in chunk.content:
                                if isinstance(item, dict) and item.get("type") == "text": text_content += item.get("text", "")
                        if text_content:
                            current_turn_node_outputs[current_panel_index] += escape(text_content)
                            current_turn_panels[current_panel_index].renderable = current_turn_node_outputs[current_panel_index]
                            new_content_added = True

                    # 2. Process Tool Call Chunks
                    if has_tool_chunks and panel_is_ai:
                        tool_chunks = getattr(chunk, 'tool_call_chunks', [])
                        for tc_chunk in tool_chunks:
                            current_id = tc_chunk.get("id")
                            current_name = tc_chunk.get("name")
                            has_args_key = 'args' in tc_chunk
                            current_args = tc_chunk.get("args")

                            # A. Start of a new tool call identified
                            if current_id and current_name:
                                active_tool_call_name = current_name
                                pending_tool_names[current_id] = current_name

                                # Print initial line only once, includes {}
                                if active_tool_call_name not in started_tool_call_line:
                                    initial_line = f"\n[dim]-> Called {escape(current_name)} Tool: {{}}[/dim]"
                                    current_turn_node_outputs[current_panel_index] += initial_line
                                    current_turn_panels[current_panel_index].renderable = current_turn_node_outputs[current_panel_index]
                                    started_tool_call_line.add(active_tool_call_name)
                                    new_content_added = True

                                # If this starting chunk *also* has args, process them now
                                if has_args_key:
                                    if process_args_fragment(current_args, active_tool_call_name, current_panel_index):
                                        new_content_added = True # Mark content added

                            # B. Args fragment for the active tool call
                            elif has_args_key and active_tool_call_name:
                                if process_args_fragment(current_args, active_tool_call_name, current_panel_index):
                                    new_content_added = True # Mark content added

                            # C. Args fragment arrived without an active tool name (warning)
                            elif has_args_key and not active_tool_call_name:
                                 args_val_str = str(current_args) if current_args is not None else ""
                                 if args_val_str and panel_is_ai: # Check panel_is_ai again just in case
                                     warning_str = f"\n[yellow]Warning: Args fragment without active tool name: '{escape(args_val_str)}'[/yellow]"
                                     current_turn_node_outputs[current_panel_index] += warning_str
                                     current_turn_panels[current_panel_index].renderable = current_turn_node_outputs[current_panel_index]
                                     new_content_added = True


                elif isinstance(chunk, ToolMessage):
                    tool_call_id = getattr(chunk, 'tool_call_id', None)
                    tool_name = pending_tool_names.get(tool_call_id, 'Unknown Tool')
                    content_display = escape(str(chunk.content)) if chunk.content is not None else "[dim](No content returned)[/dim]"
                    result_panel = Panel(content_display, title=f"<<< Tool Result ({escape(tool_name)})", border_style=TOOL_RESULT_COLOR, expand=False)

                    # Append the result panel
                    current_turn_panels.append(result_panel)
                    live_display_elements = current_turn_panels # Update the list for Live
                    new_content_added = True
                    # Reset active tool name? Probably not needed as next AIMessageChunk should provide name/id.


                if new_content_added:
                   last_processed_node = current_node # Update last node only if content was added

            except Exception as e:
                console.print(f"\n[bold red]Error processing stream event:[/bold red] {escape(str(e))}")
                traceback.print_exc()

            if new_content_added:
                live.update(Group(*live_display_elements), refresh=True)

    if not stream_finished:
        console.print("[yellow]No response stream received from AI.[/yellow]")


# --- Main loop (Updated) ---
def main():
    global current_constitution_content, current_constitution_ids, compare_mode_active, compare_constitution_sets

    console.print("Initializing models and workflow graph...")
    superego_model_instance, inner_model_instance = create_models()
    graph_app = create_workflow(superego_model=superego_model_instance, inner_model=inner_model_instance)
    console.print("Initialization complete.", style="green")

    console.print(Panel("[bold cyan]SUPEREGO CHAT SYSTEM[/bold cyan]", border_style="cyan", expand=False))
    display_help_commands()

    # Display available constitutions at startup using the imported function
    display_constitutions_table()

    thread_id = str(uuid.uuid4())
    console.print(f"\nStarting new chat thread: [cyan]{thread_id}[/cyan]")
    # Load default 'none' constitution initially using the new helper
    _load_constitutions("none")

    while True:
        try:
            prompt_prefix = f"[{USER_COLOR} bold]User:[/ {USER_COLOR} bold]"
            if compare_mode_active:
                prompt_prefix = f"[yellow bold](Compare Mode)[/] {prompt_prefix}"
            print("\n")
            user_input = console.input(prompt_prefix)

            if not user_input: continue

            # --- Command Handling (Updated) ---
            if user_input.lower().startswith('/'):
                command_parts = user_input.split(maxsplit=1)
                command = command_parts[0].lower()
                args = command_parts[1].strip() if len(command_parts) > 1 else "" # Strip args

                if command in ['/quit', '/exit']: break
                elif command == '/help':
                    display_help_commands()
                    continue
                elif command == '/history':
                    display_history(thread_id, graph_app)
                    continue
                elif command == '/new':
                    thread_id = str(uuid.uuid4())
                    console.print(f"\nStarting new chat thread: [cyan]{thread_id}[/cyan]")
                    # Keep current constitution setting for the new thread
                    _load_constitutions(CONSTITUTION_SEPARATOR.join(current_constitution_ids))
                    # Ensure compare mode is off for new thread
                    if compare_mode_active:
                         compare_mode_active = False
                         compare_constitution_sets = []
                         console.print("[yellow]Compare mode turned off.[/yellow]")
                    continue
                elif command == '/constitutions':
                    # Use the imported display function
                    display_constitutions_table()
                    continue
                elif command == '/use':
                    # Turn off compare mode if /use is called
                    if compare_mode_active:
                        console.print("[yellow]Turning off compare mode due to /use command.[/yellow]")
                        compare_mode_active = False
                        compare_constitution_sets = []
                    # Load constitutions based on args or default to 'none'
                    _load_constitutions(args if args else "none")
                    continue
                elif command == '/compare':
                    if not args:
                        console.print("[red]Usage: /compare [set1, set2+set3, ...][/red]")
                        continue
                    parsed_sets = parse_compare_sets(args)
                    if parsed_sets is not None: # Check for None explicitly, [] is valid
                         if not parsed_sets:
                              console.print("[yellow]Warning: Empty compare list provided. Compare mode not activated.[/yellow]")
                              compare_mode_active = False
                              compare_constitution_sets = []
                         else:
                              compare_constitution_sets = parsed_sets
                              compare_mode_active = True
                              sets_display = [CONSTITUTION_SEPARATOR.join(s) for s in parsed_sets]
                              console.print(f"[yellow]Compare mode activated. Next prompt will run with:[/yellow] [cyan]{', '.join(sets_display)}[/cyan]")
                    else:
                         # Error message printed by parse_compare_sets
                         compare_mode_active = False
                         compare_constitution_sets = []
                    continue
                elif command == '/compare_off':
                    if compare_mode_active:
                         compare_mode_active = False
                         compare_constitution_sets = []
                         console.print("[yellow]Compare mode turned off.[/yellow]")
                    else:
                         console.print("[dim]Compare mode is already off.[/dim]")
                    continue
                else:
                    console.print(f"[red]Unknown command: {command}. Type /help for options.[/red]")
                    continue

            # --- Graph Execution (Updated) ---
            messages_to_send = [HumanMessage(content=user_input)]

            if compare_mode_active:
                console.print(f"[yellow bold]Running in Compare Mode for {len(compare_constitution_sets)} set(s)...[/yellow bold]")
                # REMOVED: original_thread_state = graph_app.get_state(...) - Not needed

                for i, const_set_ids in enumerate(compare_constitution_sets):
                    set_name = CONSTITUTION_SEPARATOR.join(const_set_ids)
                    title = f"Run {i+1}/{len(compare_constitution_sets)} using: [cyan]{set_name}[/cyan]"

                    # Create a temporary thread ID for this comparison run
                    # Using a unique ID ensures state isolation via the checkpointer
                    temp_thread_id = f"{thread_id}_compare_{uuid.uuid4()}" # Use UUID for uniqueness

                    # REMOVED: graph_app.put_state(...) - Incorrect API usage

                    # Load constitution content for this specific set
                    # This uses the manager directly, not the global state
                    constitution_content_for_run, _ = constitution_manager.get_combined_constitution_content(const_set_ids)

                    # Run the graph and display using the temporary thread ID and specific content
                    _run_graph_and_display(graph_app, temp_thread_id, constitution_content_for_run, messages_to_send, title_prefix=title)
                    # No cleanup needed for temp thread state in DB for this example

                console.print(f"\n[yellow bold]Compare mode finished. Returning to normal mode with constitution(s): [cyan]{CONSTITUTION_SEPARATOR.join(current_constitution_ids)}[/cyan][/yellow bold]")
                compare_mode_active = False # Turn off compare mode after one prompt
                compare_constitution_sets = []

            else:
                # Normal mode: Run the graph once with the current global constitution content
                 _run_graph_and_display(graph_app, thread_id, current_constitution_content, messages_to_send)


        except KeyboardInterrupt:
            console.print("\nExiting.", style="cyan")
            break
        except Exception as e:
            console.print(f"\n[bold red]An error occurred during the turn:[/bold red] {escape(str(e))}")
            traceback.print_exc()
            # Optionally decide whether to continue or break on general errors

# --- Main execution ---
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\nInterrupted by user. Exiting.")
    except ImportError as e:
       console.print(f"[bold red]Fatal Error: A required component is missing:[/bold red] {e}")
       console.print("Please ensure all required modules are installed and accessible.")
       sys.exit(1)
    except Exception as e:
       console.print(f"[bold red]Unhandled error during execution:[/bold red] {e}")
       traceback.print_exc()
       sys.exit(1)
import sys
import json
import datetime
import uuid
import os
import traceback
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
from constitution_manager import constitution_manager
from constitution_cli import interactive_menu

# --- Rich Console & Constants ---
console = Console()
NODE_COLORS = {"superego": "yellow", "inner_agent": "green", "tools": "magenta"}
DEFAULT_NODE_COLOR = "cyan"
USER_COLOR = "blue"
TOOL_RESULT_COLOR = "magenta"

# --- Helper to create Rich Panels (for History) ---
def _create_panel_for_message(msg: BaseMessage, node_name_override: Optional[str] = None) -> Optional[Panel]:
    if isinstance(msg, HumanMessage):
        return None

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

        if node_name and node_name != "AI":
            title_node_name = node_name.replace("_", " ").title()
            color = NODE_COLORS.get(node_name, DEFAULT_NODE_COLOR)
        elif node_name_override:
             title_node_name = node_name_override.replace("_", " ").title()
             color = NODE_COLORS.get(node_name_override, DEFAULT_NODE_COLOR)

        tool_calls_str = ""
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            # Format tool calls for history view (won't stream this way)
            for tc in msg.tool_calls:
                 tool_name = escape(tc.get('name', 'N/A'))
                 try: args_display = json.dumps(tc.get('args', {}))
                 except: args_display = str(tc.get('args', {}))
                 # Use the desired format for completed calls in history
                 tool_calls_str += f"\n[dim]-> Called {tool_name} Tool: {escape(args_display)}[/dim]"

        full_content = escape(content_str.strip()) + tool_calls_str

        if full_content.strip():
            return Panel(full_content, title=f">>> {title_node_name}", border_style=color, expand=False)
        else:
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
    state = graph_app.get_state(config)
    messages = state.values.get('messages', []) if state else []

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


# --- Constitution Table Display ---
@shout_if_fails
def display_constitutions_table():
    constitutions = constitution_manager.get_available_constitutions()
    active_id = constitution_manager.get_active_constitution()
    if not constitutions:
        console.print("[yellow]No constitutions found.[/yellow]")
        return

    table = Table(title="Available Constitutions", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=15)
    table.add_column("Title", style="green")
    table.add_column("Size", justify="right", style="blue")
    table.add_column("Last Modified", style="magenta")
    for constitution in constitutions:
        id_text = f"* {constitution['id']}" if constitution["id"] == active_id else constitution["id"]
        size = f"{constitution['size'] / 1024:.1f} KB" if constitution.get('size') else "N/A"
        last_modified_ts = constitution.get("last_modified")
        last_modified = datetime.datetime.fromtimestamp(last_modified_ts).strftime("%Y-%m-%d %H:%M") if last_modified_ts else "N/A"
        table.add_row(id_text, constitution.get("title", "N/A"), size, last_modified)
    console.print(table)
    console.print(f"* Active constitution: [cyan]{active_id}[/cyan]" if active_id else "[yellow]No active constitution set.[/yellow]")

# --- Helper to Load Constitution Content ---
def _load_active_constitution() -> str:
    content = ""
    active_id = constitution_manager.get_active_constitution()
    if active_id:
        try:
            content = constitution_manager.get_constitution_content(active_id) or ""
            console.print(f"Using active constitution: [cyan]{active_id}[/cyan]")
            if not content and active_id != "none":
                 console.print(f"[yellow]Warning: Active constitution '{active_id}' loaded empty content.[/yellow]")
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load active constitution '{active_id}': {e}[/yellow]")
    return content


# --- Main loop ---
def main():
    console.print("Initializing models and workflow graph...")
    superego_model_instance, inner_model_instance = create_models()
    graph_app = create_workflow(superego_model=superego_model_instance, inner_model=inner_model_instance)
    console.print("Initialization complete.", style="green")

    console.print(Panel("[bold cyan]SUPEREGO CHAT SYSTEM[/bold cyan]", border_style="cyan", expand=False))
    console.print("- Type '/history' to view history.")
    console.print("- Type '/new' to start a new chat thread.")
    console.print("- Type '/constitutions' to manage constitutions.")
    console.print("- Type '/quit' or '/exit' to exit.")

    thread_id = str(uuid.uuid4())
    console.print(f"\nStarting new chat thread: [cyan]{thread_id}[/cyan]")
    constitution_content = _load_active_constitution()

    while True:
        try:
            config = {"configurable": {"thread_id": thread_id, "constitution": constitution_content}}

            print("\n")
            user_input = console.input(f"[{USER_COLOR} bold]User:[/ {USER_COLOR} bold]")
            if not user_input: continue

            # --- Command Handling ---
            if user_input.lower() in ['/quit', '/exit']: break
            if user_input.lower() == '/history':
                display_history(thread_id, graph_app)
                continue
            if user_input.lower() == '/new':
                thread_id = str(uuid.uuid4())
                console.print(f"\nStarting new chat thread: [cyan]{thread_id}[/cyan]")
                constitution_content = _load_active_constitution()
                continue
            if user_input.lower() == '/constitutions':
                console.print("[cyan]Entering Constitution Management...[/cyan]")
                interactive_menu()
                console.print("[cyan]...Returning to chat.[/cyan]")
                constitution_content = _load_active_constitution()
                continue

            # --- Graph Execution & STREAMING DISPLAY (Final Formatting) ---
            messages_to_send = [HumanMessage(content=user_input)]
            stream_finished = False

            # --- State for the current turn's stream ---
            live_display_elements = []
            current_turn_node_outputs: Dict[int, str] = {}
            current_turn_panels: List[Panel] = []
            last_processed_node: Optional[str] = None
            pending_tool_names: Dict[str, str] = {} # Store ID->Name map for ToolMessage title
            active_tool_call_name: Optional[str] = None # Track name of tool expecting args
            # Track which tool names have had their initial "-> Called..." line printed
            started_tool_call_line: set[str] = set()

            # --- Helper Function for Processing Args ---
            def process_args_fragment(args_fragment: Optional[str], tool_name: str, panel_idx: int) -> bool:
                """Handles appending args fragment to the correct panel."""
                nonlocal new_content_added # Allow modification of outer scope variable
                args_val_str = str(args_fragment) if args_fragment is not None else ""
                if not args_val_str: return False # No args content to add

                if tool_name not in started_tool_call_line:
                    # Args arrived before name, or name chunk was missed. Print initial line now WITH args.
                    initial_line = f"\n[dim]-> Called {escape(tool_name)} Tool: {{{escape(args_val_str)}}}[/dim]"
                    current_turn_node_outputs[panel_idx] += initial_line
                    current_turn_panels[panel_idx].renderable = current_turn_node_outputs[panel_idx]
                    started_tool_call_line.add(tool_name)
                    new_content_added = True
                else:
                    # Initial line exists, insert args before the last '}'
                    current_content = current_turn_node_outputs[panel_idx]
                    insert_marker = "}[/dim]"
                    last_marker_index = current_content.rfind(insert_marker)

                    if last_marker_index != -1:
                        insert_pos = last_marker_index
                        new_content = current_content[:insert_pos] + escape(args_val_str) + current_content[insert_pos:]
                        current_turn_node_outputs[panel_idx] = new_content
                        current_turn_panels[panel_idx].renderable = new_content
                        new_content_added = True
                    else:
                        # Fallback: Couldn't find marker, append separately (should be rare)
                        fallback_str = f"\n[dim]Args(append failed): '{escape(args_val_str)}'[/dim]"
                        current_turn_node_outputs[panel_idx] += fallback_str
                        current_turn_panels[panel_idx].renderable = current_turn_node_outputs[panel_idx]
                        new_content_added = True
                return new_content_added # Indicate if content was actually modified

            # --- Stream Processing ---
            with Live(Group(*live_display_elements), console=console, auto_refresh=False, vertical_overflow="visible") as live:
                stream_iterator = graph_app.stream({'messages': messages_to_send}, config=config, stream_mode="messages")

                for event in stream_iterator:
                    stream_finished = True
                    chunk: Optional[BaseMessage] = None
                    metadata: Dict[str, Any] = {}

                    if isinstance(event, tuple) and len(event) == 2:
                        if isinstance(event[0], BaseMessage) and isinstance(event[1], dict): chunk, metadata = event
                        else: continue
                    elif isinstance(event, BaseMessage): chunk = event
                    else: continue
                    if not chunk: continue

                    current_node = metadata.get("langgraph_node") or getattr(chunk, 'name', None)
                    if not current_node: continue

                    new_content_added = False
                    current_panel_index = len(current_turn_panels) - 1

                    try:
                        is_new_node_invocation = (current_node != last_processed_node)

                        if isinstance(chunk, AIMessageChunk):
                            has_text_content = bool(chunk.content)
                            has_tool_chunks = bool(chunk.tool_call_chunks)

                            panel_exists_or_needed = (has_text_content or has_tool_chunks) and current_node != "tools"
                            if panel_exists_or_needed:
                                if is_new_node_invocation or current_panel_index < 0:
                                    color = NODE_COLORS.get(current_node, DEFAULT_NODE_COLOR)
                                    title = f">>> {current_node.replace('_', ' ').title()}"
                                    new_panel = Panel("", title=title, border_style=color, expand=False)
                                    current_turn_panels.append(new_panel)
                                    current_panel_index = len(current_turn_panels) - 1
                                    current_turn_node_outputs[current_panel_index] = ""
                                    live_display_elements = current_turn_panels

                            panel_exists = current_panel_index >= 0

                            # 1. Process Text Content
                            if has_text_content and panel_exists:
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
                            if has_tool_chunks and panel_exists:
                                tool_chunks = getattr(chunk, 'tool_call_chunks', [])
                                for tc_chunk in tool_chunks:
                                    current_id = tc_chunk.get("id")
                                    current_name = tc_chunk.get("name")
                                    has_args_key = 'args' in tc_chunk
                                    current_args = tc_chunk.get("args")

                                    # A. Start of a new tool call identified
                                    if current_id and current_name:
                                        active_tool_call_name = current_name
                                        pending_tool_names[current_id] = current_name # Still needed for ToolMessage

                                        # Print initial line only once, includes {}
                                        if active_tool_call_name not in started_tool_call_line:
                                            initial_line = f"\n[dim]-> Called {escape(current_name)} Tool: {{}}[/dim]"
                                            current_turn_node_outputs[current_panel_index] += initial_line
                                            current_turn_panels[current_panel_index].renderable = current_turn_node_outputs[current_panel_index]
                                            started_tool_call_line.add(active_tool_call_name)
                                            new_content_added = True

                                        # If this starting chunk *also* has args, process them now
                                        if has_args_key:
                                            process_args_fragment(current_args, active_tool_call_name, current_panel_index)

                                    # B. Args fragment for the active tool call
                                    elif has_args_key and active_tool_call_name:
                                        process_args_fragment(current_args, active_tool_call_name, current_panel_index)

                                    # C. Args fragment arrived without an active tool name (warning)
                                    elif has_args_key and not active_tool_call_name:
                                         args_val_str = str(current_args) if current_args is not None else ""
                                         if args_val_str:
                                             warning_str = f"\n[yellow]Warning: Args fragment without active tool name: '{escape(args_val_str)}'[/yellow]"
                                             current_turn_node_outputs[current_panel_index] += warning_str
                                             current_turn_panels[current_panel_index].renderable = current_turn_node_outputs[current_panel_index]
                                             new_content_added = True


                        elif isinstance(chunk, ToolMessage):
                            # --- Handle Tool Message (Result) ---
                            tool_call_id = getattr(chunk, 'tool_call_id', None)
                            # Use the name stored when the ID first appeared
                            tool_name = pending_tool_names.get(tool_call_id, 'Unknown Tool')
                            content_display = escape(str(chunk.content)) if chunk.content is not None else "[dim](No content returned)[/dim]"
                            result_panel = Panel(content_display, title=f"<<< Tool Result ({escape(tool_name)})", border_style=TOOL_RESULT_COLOR, expand=False)
                            current_turn_panels.append(result_panel)
                            live_display_elements = current_turn_panels
                            new_content_added = True
                            # Reset active tool name? Not strictly necessary, new call will overwrite
                            # active_tool_call_name = None


                        # Update last processed node *if* content was added or panel created
                        if new_content_added:
                           last_processed_node = current_node

                    except Exception as e:
                        console.print(f"\n[bold red]Error processing stream event:[/bold red] {escape(str(e))}")
                        traceback.print_exc()

                    # Refresh the live display only if changes occurred
                    if new_content_added:
                        live.update(Group(*live_display_elements), refresh=True)
                # End of stream loop

            if not stream_finished:
                console.print("[yellow]No response stream received from AI.[/yellow]")

        except KeyboardInterrupt:
            console.print("\nExiting.", style="cyan")
            break
        except Exception as e:
            console.print(f"\n[bold red]An error occurred during the turn:[/bold red] {escape(str(e))}")
            traceback.print_exc()

# --- Main execution ---
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\nInterrupted by user. Exiting.")
    except ImportError as e:
       console.print(f"[bold red]Fatal Error: A required component is missing:[/bold red] {e}")
       console.print("Please ensure all required modules (superego_core, config, constitution_manager, etc.) are installed and accessible.")
       sys.exit(1)
    except Exception as e:
       console.print(f"[bold red]Unhandled error during execution:[/bold red] {e}")
       traceback.print_exc()
       sys.exit(1)
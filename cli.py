# cli.py (Refactored)
import sys
import json
import datetime
import uuid
import os
import pprint
import traceback
from typing import List, Optional, Dict, Any, Union

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk
from rich.console import Console, Group
from rich.panel import Panel
from rich.live import Live
from rich.markup import escape
from rich.table import Table
from utils import shout_if_fails

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
            elif isinstance(msg, (AIMessage, AIMessageChunk)):
                content_str = "";
                if isinstance(msg.content, str): content_str = msg.content
                elif isinstance(msg.content, list):
                     for item in msg.content:
                         if isinstance(item, dict) and item.get("type") == "text": content_str += item.get("text", "")
                has_tool_calls = hasattr(msg, 'tool_calls') and msg.tool_calls; has_tool_chunks = hasattr(msg, 'tool_call_chunks') and msg.tool_call_chunks
                if content_str.strip() or has_tool_calls or has_tool_chunks:
                    title = "AI"; node_name = getattr(msg, 'name', None)
                    if node_name and node_name != "tools": title = node_name.replace("_"," ").title()
                    color = NODE_COLORS.get(node_name, NODE_COLORS.get("inner_agent"))
                    tool_calls_str = "\n[dim](Tool used)[/dim]" if has_tool_calls or has_tool_chunks else ""
                    full_content = escape(content_str.strip()) + tool_calls_str
                    if full_content or tool_calls_str: history_renderables.append(Panel(full_content, title=f">>> {title}", border_style=color, expand=False))
            elif isinstance(msg, ToolMessage):
                 content_display = escape(str(msg.content)) if msg.content is not None else "[dim](No content returned)[/dim]"
                 history_renderables.append(Panel(content_display, title=f"<<< Tool Result ({escape(msg.name)})", border_style=TOOL_RESULT_COLOR, expand=False))

    console.print(Group(*history_renderables))
    console.print("--------------------\n", style="bold blue")


# --- Constitution Table Display ---
@shout_if_fails 
def display_constitutions_table():
    constitutions = constitution_manager.get_available_constitutions()
    active_id = constitution_manager.get_active_constitution()
    if not constitutions: console.print("[yellow]No constitutions found.[/yellow]"); return

    table = Table(title="Available Constitutions", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", width=15); table.add_column("Title", style="green")
    table.add_column("Size", justify="right", style="blue"); table.add_column("Last Modified", style="magenta")
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
    """Loads content of the active constitution, returns empty string on failure."""
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

            # Command Handling
            if user_input.lower() in ['/quit', '/exit']: break
            if user_input.lower() == '/history': display_history(thread_id, graph_app); continue # Call decorated function
            if user_input.lower() == '/new':
                thread_id = str(uuid.uuid4()); console.print(f"\nStarting new chat thread: [cyan]{thread_id}[/cyan]")
                constitution_content = _load_active_constitution(); continue
            if user_input.lower() == '/constitutions':
                console.print("[cyan]Entering Constitution Management...[/cyan]")
                interactive_menu() # Call directly, let main loop catch errors if any
                console.print("[cyan]...Returning to chat.[/cyan]")
                constitution_content = _load_active_constitution(); continue

            # Graph Execution & Display
            messages_to_send = [HumanMessage(content=user_input)]
            turn_components = []; current_panel_refs = {}; current_panel_contents = {}
            pending_tool_input = {}; processed_tool_call_ids = set()
            current_node_name = None; last_component_added = "start"; stream_finished = False

            with Live(Group(*turn_components), console=console, auto_refresh=False, vertical_overflow="visible") as live:
                for yielded_item in graph_app.stream({'messages': messages_to_send}, config=config, stream_mode="messages"):
                    stream_finished = True; message_chunk = None; metadata = {}
                    if isinstance(yielded_item, tuple) and len(yielded_item) == 2 and isinstance(yielded_item[0], BaseMessage) and isinstance(yielded_item[1], dict): message_chunk, metadata = yielded_item
                    elif isinstance(yielded_item, BaseMessage): message_chunk = yielded_item
                    else: continue
                    if not message_chunk: continue

                    node_name = metadata.get("langgraph_node")
                    new_content_added = False
                    try:
                        if isinstance(message_chunk, (AIMessage, AIMessageChunk)):
                            content_list = [];
                            if isinstance(message_chunk.content, str): content_list.append({"type": "text", "text": message_chunk.content})
                            elif isinstance(message_chunk.content, list): content_list = message_chunk.content
                            tool_calls = getattr(message_chunk, 'tool_calls', []); tool_chunks = getattr(message_chunk, 'tool_call_chunks', [])
                            for item in content_list:
                                if isinstance(item, dict):
                                    item_type = item.get("type")
                                    if item_type == "text":
                                        text_content = item.get("text", ""); current_processing_node = node_name or getattr(message_chunk, 'name', None)
                                        if text_content and current_processing_node and current_processing_node != "tools":
                                            color = NODE_COLORS.get(current_processing_node, DEFAULT_NODE_COLOR); title = f">>> {current_processing_node.replace('_', ' ').title()}"
                                            if current_processing_node not in current_panel_refs or last_component_added != "agent" or current_node_name != current_processing_node:
                                                current_node_name = current_processing_node; current_panel_contents[current_node_name] = escape(text_content)
                                                new_panel = Panel(current_panel_contents[current_node_name], title=title, border_style=color, expand=False)
                                                current_panel_refs[current_node_name] = new_panel; turn_components.append(new_panel); last_component_added = "agent"
                                            else:
                                                current_panel_contents[current_node_name] += escape(text_content); panel_ref = current_panel_refs.get(current_node_name)
                                                if panel_ref: panel_ref.renderable = current_panel_contents[current_node_name]
                                            new_content_added = True
                            if tool_calls:
                                for tool_call in tool_calls:
                                    tool_call_id = tool_call.get("id"); tool_name = tool_call.get("name"); tool_args = tool_call.get("args")
                                    if tool_call_id and tool_name and tool_args is not None and tool_call_id not in processed_tool_call_ids:
                                        calling_agent = node_name or getattr(message_chunk,'name', current_node_name); agent_display = calling_agent.replace('_',' ').title() if calling_agent else "Agent"; tool_display_name = escape(tool_name)
                                        try: input_display = escape(json.dumps(tool_args))
                                        except TypeError: input_display = escape(str(tool_args))
                                        tool_call_info = f"\n[dim]{agent_display} used {tool_display_name}. Input: {input_display}[/dim]"
                                        if calling_agent and calling_agent in current_panel_contents:
                                            current_panel_contents[calling_agent] += tool_call_info; panel_ref = current_panel_refs.get(calling_agent)
                                            if panel_ref: panel_ref.renderable = current_panel_contents[calling_agent]
                                            last_component_added = "tool_call"; new_content_added = True
                                        processed_tool_call_ids.add(tool_call_id)
                            if tool_chunks:
                                for tool_chunk in tool_chunks:
                                    tool_call_id = tool_chunk.get("id"); tool_name = tool_chunk.get("name"); tool_args_chunk = tool_chunk.get("args")
                                    if tool_call_id and tool_name:
                                        calling_agent = node_name or getattr(message_chunk, 'name', current_node_name)
                                        if tool_call_id not in pending_tool_input: pending_tool_input[tool_call_id] = {"name": tool_name, "input_str": "", "agent": calling_agent}
                                        if tool_args_chunk: pending_tool_input[tool_call_id]["input_str"] += tool_args_chunk
                                        current_input_str = pending_tool_input[tool_call_id]["input_str"]; is_complete = False; formatted_input = ""
                                        try: parsed_input = json.loads(current_input_str); formatted_input = json.dumps(parsed_input); is_complete = True
                                        except json.JSONDecodeError: pass
                                        if is_complete and tool_call_id not in processed_tool_call_ids:
                                            agent_name = pending_tool_input[tool_call_id]["agent"]; agent_display = agent_name.replace('_',' ').title() if agent_name else "Agent"; tool_display_name = escape(pending_tool_input[tool_call_id]["name"]); input_display = escape(formatted_input)
                                            tool_call_info = f"\n[dim]{agent_display} used {tool_display_name}. Input: {input_display}[/dim]"
                                            if agent_name and agent_name in current_panel_contents:
                                                current_panel_contents[agent_name] += tool_call_info; panel_ref = current_panel_refs.get(agent_name)
                                                if panel_ref: panel_ref.renderable = current_panel_contents[agent_name]
                                                last_component_added = "tool_call"; new_content_added = True
                                            processed_tool_call_ids.add(tool_call_id)
                        elif isinstance(message_chunk, ToolMessage):
                            tool_name = escape(message_chunk.name); tool_content = escape(str(message_chunk.content)) if message_chunk.content is not None else "[dim](No content returned)[/dim]"
                            result_panel = Panel(tool_content, title=f"<<< Tool Result ({tool_name})", border_style=TOOL_RESULT_COLOR, expand=False)
                            turn_components.append(result_panel); last_component_added = "tool_result"; current_node_name = "tools"; new_content_added = True
                    except Exception as e:
                        console.print(f"\n[bold red]Error processing chunk:[/bold red] {escape(str(e))}",)
                        traceback.print_exc()

                    if new_content_added:
                        live.update(Group(*turn_components), refresh=True)

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
    except Exception as e: # Catch fatal errors during setup via @shout_if_fails or others
        console.print(f"[bold red]Unhandled error during execution:[/bold red] {e}")
        traceback.print_exc()
        sys.exit(1)
# superego-lgdemo/cli.py (v4 - Integrates provided constitution_cli.py & Configurable Constitution)
import sys
import json
import datetime # Added for timestamp formatting
from typing import List, Optional, Dict, Any, Union

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, ToolMessage, AIMessageChunk

from rich.console import Console, Group
from rich.panel import Panel
from rich.live import Live
from rich.markup import escape
from rich.table import Table # For constitutions

# Assuming superego_core is structured correctly and graph is exposed
# Ensure the graph imported here is the one created by the modified create_workflow
from superego_core import graph, get_or_create_session, get_all_sessions, get_message_history, SessionState, session_manager
from config import CONFIG

# --- Import Constitution Management ---
# Use the constitution_manager instance directly as in constitution_cli.py
try:
    from constitution_manager import constitution_manager
    from constitution_cli import interactive_menu # Use the interactive menu function
    constitution_cli_available = True
except ImportError:
    constitution_manager = None
    interactive_menu = None
    constitution_cli_available = False
    print("[yellow]Warning: constitution_manager.py or constitution_cli.py not found or functions missing. Constitution features disabled.[/yellow]")


# --- Rich Console ---
console = Console()

# --- Node Colors ---
NODE_COLORS = {
    "superego": "yellow",
    "inner_agent": "green",
    "tools": "magenta", # Color for the result panel title
}
DEFAULT_NODE_COLOR = "cyan"
USER_COLOR = "blue" # Used for user prompt prefix
TOOL_RESULT_COLOR = "magenta" # Used for tool result panel border

# --- History Display (Panels per message) ---
def display_history(session_id: str):
    """Displays the message history for the session using Rich Panels."""
    console.print("\n--- Chat History ---", style="bold blue")
    try:
        # Assuming get_message_history correctly fetches from the checkpointer
        messages: List[BaseMessage] = get_message_history(session_id)
        history_renderables = []
        if not messages:
            history_renderables.append("[dim]No messages yet.[/dim]")
        else:
            for msg in messages:
                if isinstance(msg, HumanMessage):
                     history_renderables.append(f"[{USER_COLOR} bold]User:[/ {USER_COLOR} bold] {escape(msg.content)}")
                elif isinstance(msg, (AIMessage, AIMessageChunk)):
                    title = "AI"
                    node_name = getattr(msg, 'name', None) # Use name if available (set by checkpointer?)
                    if node_name and node_name != "tools": # Don't title panels "Tools"
                         title = node_name.replace("_"," ").title()

                    color = NODE_COLORS.get(node_name, NODE_COLORS.get("inner_agent")) # Default to inner_agent color

                    content_str = ""
                    tool_calls_str = ""
                    if isinstance(msg.content, str):
                         content_str = msg.content
                    elif isinstance(msg.content, list): # Handle potential list content (e.g., from tool use blocks)
                         for item in msg.content:
                             if isinstance(item, dict):
                                 if item.get("type") == "text":
                                     content_str += item.get("text", "")
                    # Check for tool_calls attribute (common for AIMessage)
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                         tool_calls_str = "\n[dim](Tool used)[/dim]"
                    # Check for tool_call_chunks attribute (common for AIMessageChunk)
                    elif hasattr(msg, 'tool_call_chunks') and msg.tool_call_chunks:
                         tool_calls_str = "\n[dim](Tool used)[/dim]"

                    full_content = escape(content_str.strip()) + tool_calls_str
                    if full_content: # Only add panel if there's content
                         history_renderables.append(Panel(full_content, title=f">>> {title}", border_style=color, expand=False))

                elif isinstance(msg, ToolMessage):
                     history_renderables.append(Panel(escape(str(msg.content)), title=f"<<< Tool Result ({escape(msg.name)})", border_style=TOOL_RESULT_COLOR, expand=False))

        console.print(Group(*history_renderables))

    except Exception as e:
        console.print(f"[bold red]Error retrieving history for {session_id}:[/bold red] {e}")
    console.print("--------------------\n", style="bold blue")


# --- Display Constitutions Table (using constitution_manager) ---
def display_constitutions_table():
    """Loads constitutions via constitution_manager and displays them in a Rich Table."""
    if not constitution_manager:
        console.print("[yellow]Constitution Manager not available.[/yellow]")
        return

    try:
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

    except Exception as e:
        console.print(f"[bold red]Error loading or displaying constitutions:[/bold red] {e}")


# --- Session Selection with Constitutions ---
def select_session() -> str:
    """Allows user to select an existing session or create a new one, showing constitutions."""
    # Display Constitutions First
    if constitution_cli_available:
        display_constitutions_table()
        console.print() # Add spacing

    # Session Selection Logic
    sessions = get_all_sessions()
    if not sessions:
        console.print("No existing sessions found. Creating a new one.")
        return get_or_create_session()

    console.print("Available sessions:", style="bold cyan")
    for i, session_id in enumerate(sessions):
        console.print(f"{i + 1}. {session_id}")

    while True:
        choice = console.input("[cyan]Select session number or press Enter for a new session:[/cyan] ")
        if choice.lower() == 'new' or choice.lower() == '':
            new_id = get_or_create_session()
            console.print(f"Created new session: {new_id}", style="green")
            return new_id
        try:
            index = int(choice) - 1
            if 0 <= index < len(sessions):
                selected_id = sessions[index]
                console.print(f"Selected session: {selected_id}", style="green")
                return selected_id
            else:
                console.print("Invalid session number.", style="red")
        except ValueError:
            console.print("Invalid input. Please enter a number or 'new'.", style="red")

# --- Main loop ---
def main():
    """Main CLI loop managing a Live Group of Panels."""
    console.print(Panel("[bold cyan]SUPEREGO CHAT SYSTEM[/bold cyan]", border_style="cyan", expand=False))
    console.print(f"Type '/history' for history, '/quit' or '/exit' to exit.{' /constitutions to manage.' if constitution_cli_available else ''}")

    session_id = select_session()

    active_constitution_id = None
    constitution_content = "" 
    if constitution_manager:
        active_constitution_id = constitution_manager.get_active_constitution()
        if active_constitution_id:
             console.print(f"Using active constitution for this session: [cyan]{active_constitution_id}[/cyan]")
             constitution_content = constitution_manager.get_constitution_content(active_constitution_id)
             if not constitution_content:
                 console.print(f"[yellow]Warning: Could not load content for constitution '{active_constitution_id}'. Superego will use default instructions only.[/yellow]")
                 constitution_content = ""
        else:
             console.print("[yellow]No active constitution set in manager. Superego will use default instructions only.[/yellow]")
    else:
        console.print("[yellow]Constitution manager not available. Superego will use default instructions only.[/yellow]")

    # --- MODIFIED: Graph configuration - add loaded constitution content ---
    config = {
        "configurable": {
            "thread_id": session_id,
            "constitution": constitution_content  # Pass the loaded string content
        }
    }
    # --- End Modifications for Constitution Config ---


    while True:
        try:
            # Add spacing before user prompt
            print("\n")
            user_input = console.input(f"[{USER_COLOR} bold]User:[/ {USER_COLOR} bold]")
            if not user_input:
                continue
            if user_input.lower() in ['/quit', '/exit']:
                console.print("Exiting.", style="cyan")
                break
            if user_input.lower() == '/history':
                display_history(session_id)
                continue
            if user_input.lower() == '/constitutions' and constitution_cli_available:
                console.print("[cyan]Entering Constitution Management...[/cyan]")
                interactive_menu() # Call the imported function
                console.print("[cyan]Exiting Constitution Management. Returning to chat.[/cyan]")
                # Reload constitution content in case the active one changed
                if constitution_manager:
                     active_constitution_id = constitution_manager.get_active_constitution()
                     if active_constitution_id:
                         console.print(f"Active constitution is now: [cyan]{active_constitution_id}[/cyan]")
                         constitution_content = constitution_manager.get_constitution_content(active_constitution_id) or ""
                         # Update config for subsequent calls in this session
                         config["configurable"]["constitution"] = constitution_content
                     else:
                         console.print("[yellow]No active constitution set after management.[/yellow]")
                         config["configurable"]["constitution"] = ""
                continue # Go back to prompt user input in main chat

            # --- State for the current turn ---
            turn_components: List[Union[Panel, str]] = []
            current_panel_refs: Dict[str, Panel] = {}
            current_panel_contents: Dict[str, str] = {}
            pending_tool_input: Dict[str, Dict[str, str]] = {}
            processed_tool_call_ids = set()
            current_node_name = None
            last_component_added = "start"

            # User input is not added as a panel

            stream = graph.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=config, # Pass the config containing thread_id and constitution
                stream_mode="messages"
            )

            stream_finished = False

            with Live(Group(*turn_components), console=console, auto_refresh=False, vertical_overflow="visible") as live:

                for chunk_tuple in stream:
                    stream_finished = True
                    # Handle potential variations in stream output format
                    if isinstance(chunk_tuple, list) and len(chunk_tuple) > 0:
                         message_chunk: BaseMessage = chunk_tuple[0]
                         metadata: Dict[str, Any] = chunk_tuple[1] if len(chunk_tuple) > 1 else {}
                    elif isinstance(chunk_tuple, BaseMessage): # Simpler format?
                         message_chunk = chunk_tuple
                         metadata = {} # No metadata in this format
                    else:
                         console.print(f"\n[red]Unexpected stream format: {type(chunk_tuple)}[/red]")
                         continue # Skip this chunk

                    # Extract node name from metadata if available
                    node_name = metadata.get("langgraph_node")
                    new_content_added = False # Flag to trigger refresh

                    try:
                        # --- AI Message / Chunk ---
                        if isinstance(message_chunk, (AIMessage, AIMessageChunk)):
                            content_list = []
                            # Handle both string and list content types robustly
                            if isinstance(message_chunk.content, str):
                                content_list.append({"type": "text", "text": message_chunk.content})
                            elif isinstance(message_chunk.content, list):
                                content_list = message_chunk.content # Assume it's already in the correct format

                            for item in content_list:
                                if isinstance(item, dict):
                                    item_type = item.get("type")

                                    # --- Text Content ---
                                    if item_type == "text":
                                        text_content = item.get("text", "")
                                        # Use node_name from metadata if available, else try AIMessage.name
                                        current_processing_node = node_name or getattr(message_chunk, 'name', None)

                                        if text_content and current_processing_node and current_processing_node != "tools":
                                            color = NODE_COLORS.get(current_processing_node, DEFAULT_NODE_COLOR)
                                            title = f">>> {current_processing_node.replace('_', ' ').title()}"

                                            if current_processing_node not in current_panel_refs or last_component_added != "agent" or current_node_name != current_processing_node:
                                                # New agent panel needed
                                                current_node_name = current_processing_node
                                                current_panel_contents[current_node_name] = escape(text_content)
                                                new_panel = Panel(
                                                    current_panel_contents[current_node_name],
                                                    title=title,
                                                    border_style=color,
                                                    expand=False
                                                )
                                                current_panel_refs[current_node_name] = new_panel
                                                turn_components.append(new_panel)
                                                last_component_added = "agent"
                                            else:
                                                # Append to existing agent panel
                                                current_panel_contents[current_node_name] += escape(text_content)
                                                panel_ref = current_panel_refs.get(current_node_name)
                                                if panel_ref:
                                                    panel_ref.renderable = current_panel_contents[current_node_name]

                                            new_content_added = True

                                    # --- Tool Call Info (from AIMessageChunk) ---
                                    elif item_type == "tool_call_chunk":
                                        tool_call_id = item.get("id")
                                        tool_name = item.get("name")
                                        tool_args_chunk = item.get("args") # This is a string chunk

                                        if tool_call_id and tool_name:
                                            # Determine the agent calling the tool
                                            calling_agent = node_name or getattr(message_chunk, 'name', current_node_name)

                                            if tool_call_id not in pending_tool_input:
                                                pending_tool_input[tool_call_id] = {"name": tool_name, "input_str": "", "agent": calling_agent}

                                            if tool_args_chunk:
                                                pending_tool_input[tool_call_id]["input_str"] += tool_args_chunk

                                            # Check if the accumulated input is complete JSON
                                            current_input_str = pending_tool_input[tool_call_id]["input_str"]
                                            is_complete = False; formatted_input = ""
                                            try:
                                                parsed_input = json.loads(current_input_str)
                                                formatted_input = json.dumps(parsed_input) # Use compact dumps for display
                                                is_complete = True
                                            except json.JSONDecodeError: pass

                                            # If complete JSON AND not yet processed, append info to the agent panel
                                            if is_complete and tool_call_id not in processed_tool_call_ids:
                                                agent_name = pending_tool_input[tool_call_id]["agent"]
                                                agent_display = agent_name.replace('_', ' ').title() if agent_name else "Agent"
                                                tool_display_name = escape(tool_name)
                                                input_display = escape(formatted_input)
                                                tool_call_info = f"\n[dim]{agent_display} used {tool_display_name} tool. Input: {input_display}[/dim]"

                                                # Append to the content string of the calling agent's panel
                                                if agent_name and agent_name in current_panel_contents:
                                                     current_panel_contents[agent_name] += tool_call_info
                                                     panel_ref = current_panel_refs.get(agent_name)
                                                     if panel_ref:
                                                         panel_ref.renderable = current_panel_contents[agent_name]
                                                     last_component_added = "tool_call" # Mark that a tool call was added
                                                     new_content_added = True

                                                processed_tool_call_ids.add(tool_call_id) # Mark as processed

                            # Also handle tool_calls attribute if present (often on final AIMessage)
                            if hasattr(message_chunk, 'tool_calls') and message_chunk.tool_calls:
                                 for tool_call in message_chunk.tool_calls:
                                     tool_call_id = tool_call.get("id")
                                     tool_name = tool_call.get("name")
                                     tool_args = tool_call.get("args") # Usually a dict here

                                     if tool_call_id and tool_name and tool_args is not None and tool_call_id not in processed_tool_call_ids:
                                         # Determine the agent calling the tool
                                         calling_agent = node_name or getattr(message_chunk, 'name', current_node_name)
                                         agent_display = calling_agent.replace('_', ' ').title() if calling_agent else "Agent"
                                         tool_display_name = escape(tool_name)
                                         try: # Ensure args are displayed as JSON string
                                             input_display = escape(json.dumps(tool_args))
                                         except TypeError:
                                             input_display = escape(str(tool_args)) # Fallback

                                         tool_call_info = f"\n[dim]{agent_display} used {tool_display_name} tool. Input: {input_display}[/dim]"

                                         if calling_agent and calling_agent in current_panel_contents:
                                              current_panel_contents[calling_agent] += tool_call_info
                                              panel_ref = current_panel_refs.get(calling_agent)
                                              if panel_ref:
                                                  panel_ref.renderable = current_panel_contents[calling_agent]
                                              last_component_added = "tool_call"
                                              new_content_added = True

                                         processed_tool_call_ids.add(tool_call_id)


                        # --- Tool Result (ToolMessage) ---
                        elif isinstance(message_chunk, ToolMessage):
                             tool_name = escape(message_chunk.name)
                             tool_content = escape(str(message_chunk.content))
                             result_panel = Panel(tool_content, title=f"<<< Tool Result ({tool_name})", border_style=TOOL_RESULT_COLOR, expand=False)
                             turn_components.append(result_panel)
                             last_component_added = "tool_result"
                             current_node_name = "tools" # Assume tool results come from the 'tools' node conceptually
                             new_content_added = True

                    except Exception as e:
                         console.print(f"\n[bold red]Error processing chunk:[/bold red] {escape(str(e))}",)
                         # import traceback; traceback.print_exc() # Uncomment for debugging

                    # --- Update Live Display ---
                    if new_content_added:
                        live.update(Group(*turn_components), refresh=True)

            # Handle cases where the stream might not yield anything
            if not stream_finished:
                 turn_components.append("[yellow]No response received from AI for this input.[/yellow]")
                 if not turn_components: 
                      console.print("[yellow]No response received from AI for this input.[/yellow]")
                 else:
                      live.update(Group(*turn_components), refresh=True)


        except KeyboardInterrupt:
            console.print("\nExiting.", style="cyan")
            break
        except Exception as e:
            console.print(f"\n[bold red]An error occurred:[/bold red] {escape(str(e))}")
            # import traceback; traceback.print_exc() # Uncomment for debugging full traceback

if __name__ == "__main__":
    main()
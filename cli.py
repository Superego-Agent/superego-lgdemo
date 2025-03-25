# superego-lgdemo/cli.py (v4 - Integrates provided constitution_cli.py)
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

# --- History Display (Panels per message - unchanged) ---
def display_history(session_id: str):
    """Displays the message history for the session using Rich Panels."""
    console.print("\n--- Chat History ---", style="bold blue")
    try:
        messages: List[BaseMessage] = get_message_history(session_id)
        history_renderables = []
        if not messages:
            # console.print("No messages yet.") # Let Group handle empty
            history_renderables.append("[dim]No messages yet.[/dim]")
        else:
            for msg in messages:
                if isinstance(msg, HumanMessage):
                     # History shows user input without panel for consistency now
                     history_renderables.append(f"[{USER_COLOR} bold]User:[/ {USER_COLOR} bold] {escape(msg.content)}")
                elif isinstance(msg, (AIMessage, AIMessageChunk)):
                    title = "AI"
                    node_name = getattr(msg, 'name', None)
                    if node_name and node_name != "tools":
                        title = node_name.replace("_"," ").title()

                    color = NODE_COLORS.get(node_name, NODE_COLORS.get("inner_agent"))

                    content_str = ""
                    tool_calls_str = ""
                    # Simplified content extraction for history display
                    if isinstance(msg.content, str):
                         content_str = msg.content
                    elif isinstance(msg.content, list):
                         for item in msg.content:
                             if isinstance(item, dict):
                                 if item.get("type") == "text":
                                     content_str += item.get("text", "")
                                 # We don't show full tool calls in history for brevity, just indicate they happened
                    if msg.tool_calls:
                         tool_calls_str = "\n[dim](Tool used)[/dim]"

                    full_content = escape(content_str.strip()) + tool_calls_str
                    if full_content:
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

    # --- Selecting Constitution for the Session ---
    active_constitution_id = None
    if constitution_manager:
        active_constitution_id = constitution_manager.get_active_constitution()
        console.print(f"Using active constitution: [cyan]{active_constitution_id}[/cyan]")
        # Potentially prompt user to select a constitution here if desired
        # selected_constitution_id = typer.prompt(f"Enter constitution ID to use (default: {active_constitution_id})", default=active_constitution_id)
        # if selected_constitution_id != active_constitution_id:
        #    success, msg = constitution_manager.set_active_constitution(selected_constitution_id) # This might affect global state - consider graph config instead
        #    if success: active_constitution_id = selected_constitution_id
        #    else: console.print(f"[red]Failed to set constitution: {msg}[/red]")

    # Graph configuration
    config = {"configurable": {"thread_id": session_id}}
    # How to pass the selected constitution to the graph depends on your graph's design.
    # Option 1: Pass ID via config (if graph supports it)
    # if active_constitution_id:
    #    config["configurable"]["constitution_id"] = active_constitution_id
    # Option 2: Graph reads from constitution_manager directly (simplest if manager holds global state)
    # Option 3: Load content and pass via config (might be large)
    # content = constitution_manager.get_constitution_content(active_constitution_id)
    # if content: config["configurable"]["constitution_content"] = content


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
                # Call the interactive menu from constitution_cli.py
                console.print("[cyan]Entering Constitution Management...[/cyan]")
                interactive_menu() # Call the imported function
                console.print("[cyan]Exiting Constitution Management. Returning to chat.[/cyan]")
                # Re-display active constitution in case it changed
                if constitution_manager:
                     active_constitution_id = constitution_manager.get_active_constitution()
                     console.print(f"Active constitution is now: [cyan]{active_constitution_id}[/cyan]")
                continue # Go back to prompt user input in main chat

            # --- State for the current turn ---
            turn_components: List[Union[Panel, str]] = [] # Holds Panel objects mainly
            current_panel_refs: Dict[str, Panel] = {} # Store references to active agent panels {node_name: panel_object}
            current_panel_contents: Dict[str, str] = {} # Store raw content string {node_name: content_string}
            pending_tool_input: Dict[str, Dict[str, str]] = {}
            processed_tool_call_ids = set()
            current_node_name = None # Track the active node name
            last_component_added = "start"

            # User input is NOT added as a panel anymore

            stream = graph.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
                stream_mode="messages"
            )

            stream_finished = False

            with Live(Group(*turn_components), console=console, auto_refresh=False, vertical_overflow="visible") as live:

                for chunk_tuple in stream:
                    stream_finished = True
                    message_chunk: BaseMessage = chunk_tuple[0]
                    metadata: Dict[str, Any] = chunk_tuple[1] if len(chunk_tuple) > 1 else {}
                    node_name = metadata.get("langgraph_node")
                    new_content_added = False # Flag to trigger refresh

                    try:
                        if isinstance(message_chunk, (AIMessage, AIMessageChunk)):
                            if isinstance(message_chunk.content, list):
                                for item in message_chunk.content:
                                    if isinstance(item, dict):
                                        item_type = item.get("type")

                                        # --- Text Content ---
                                        if item_type == "text":
                                            text_content = item.get("text", "")
                                            if text_content and node_name and node_name != "tools":
                                                color = NODE_COLORS.get(node_name, DEFAULT_NODE_COLOR)
                                                title = f">>> {node_name.replace('_', ' ').title()}"

                                                if node_name not in current_panel_refs or last_component_added != "agent" or current_node_name != node_name:
                                                    # New agent panel needed
                                                    current_node_name = node_name
                                                    current_panel_contents[node_name] = escape(text_content)
                                                    new_panel = Panel(
                                                        current_panel_contents[node_name],
                                                        title=title,
                                                        border_style=color,
                                                        expand=False
                                                    )
                                                    current_panel_refs[node_name] = new_panel
                                                    turn_components.append(new_panel)
                                                    last_component_added = "agent"
                                                else:
                                                    # Append to existing agent panel
                                                    current_panel_contents[node_name] += escape(text_content)
                                                    # Try updating the renderable content directly
                                                    panel_ref = current_panel_refs.get(node_name)
                                                    if panel_ref:
                                                         panel_ref.renderable = current_panel_contents[node_name]

                                                new_content_added = True

                                        # --- Tool Call Info ---
                                        elif item_type == "tool_use":
                                            # (Tool call accumulation logic remains the same)
                                            tool_call_id = item.get("id")
                                            tool_name = item.get("name")
                                            if tool_call_id and tool_name:
                                                if tool_call_id not in pending_tool_input:
                                                    pending_tool_input[tool_call_id] = {"name": tool_name, "input_str": "", "agent": node_name or current_node_name}
                                                if "partial_json" in item:
                                                    pending_tool_input[tool_call_id]["input_str"] += item["partial_json"]

                                                current_input_str = pending_tool_input[tool_call_id]["input_str"]
                                                is_complete = False; formatted_input = ""
                                                try:
                                                    parsed_input = json.loads(current_input_str)
                                                    formatted_input = json.dumps(parsed_input)
                                                    is_complete = True
                                                except json.JSONDecodeError: pass

                                                if is_complete and tool_call_id not in processed_tool_call_ids:
                                                    agent_name = pending_tool_input[tool_call_id]["agent"]
                                                    agent_display = agent_name.replace('_', ' ').title() if agent_name else "Agent"
                                                    tool_display_name = escape(tool_name)
                                                    input_display = escape(formatted_input)
                                                    tool_call_info = f"\n[dim]{agent_display} used {tool_display_name} tool. Input: {input_display}[/dim]"

                                                    # Append to the content string and update the Panel ref
                                                    last_agent_node = agent_name or current_node_name
                                                    if last_agent_node and last_agent_node in current_panel_contents:
                                                         current_panel_contents[last_agent_node] += tool_call_info
                                                         panel_ref = current_panel_refs.get(last_agent_node)
                                                         if panel_ref:
                                                             panel_ref.renderable = current_panel_contents[last_agent_node]
                                                         last_component_added = "tool_call"
                                                         new_content_added = True

                                                    processed_tool_call_ids.add(tool_call_id)

                            elif isinstance(message_chunk.content, str): # Fallback simple string content
                                text_content = message_chunk.content.strip()
                                if text_content and node_name and node_name != "tools":
                                    color = NODE_COLORS.get(node_name, DEFAULT_NODE_COLOR)
                                    title = f">>> {node_name.replace('_', ' ').title()}"
                                    if node_name not in current_panel_refs or last_component_added != "agent" or current_node_name != node_name:
                                        current_node_name = node_name
                                        current_panel_contents[node_name] = escape(text_content)
                                        new_panel = Panel(current_panel_contents[node_name], title=title, border_style=color, expand=False)
                                        current_panel_refs[node_name] = new_panel
                                        turn_components.append(new_panel)
                                        last_component_added = "agent"
                                    else:
                                        current_panel_contents[node_name] += escape(text_content)
                                        panel_ref = current_panel_refs.get(node_name)
                                        if panel_ref:
                                             panel_ref.renderable = current_panel_contents[node_name]
                                    new_content_added = True

                        # --- Tool Result (ToolMessage) ---
                        elif isinstance(message_chunk, ToolMessage):
                             tool_name = escape(message_chunk.name)
                             tool_content = escape(str(message_chunk.content))
                             result_panel = Panel(tool_content, title=f"<<< Tool Result ({tool_name})", border_style=TOOL_RESULT_COLOR, expand=False)
                             turn_components.append(result_panel)
                             last_component_added = "tool_result"
                             current_node_name = "tools"
                             new_content_added = True

                    except Exception as e:
                         console.print(f"\n[bold red]Error processing chunk:[/bold red] {escape(str(e))}",)

                    # --- Update Live Display ---
                    if new_content_added:
                        live.update(Group(*turn_components), refresh=True) # Force refresh


            # Final update/cleanup outside loop might not be needed if refresh=True works
            if not stream_finished:
                 # Add message if no stream chunks were received
                 turn_components.append("[yellow]No response received from AI.[/yellow]")
                 live.update(Group(*turn_components), refresh=True)


        except KeyboardInterrupt:
            console.print("\nExiting.", style="cyan")
            break
        except Exception as e:
            console.print(f"\n[bold red]An error occurred:[/bold red] {escape(str(e))}")
            # import traceback; traceback.print_exc()

if __name__ == "__main__":
    main()
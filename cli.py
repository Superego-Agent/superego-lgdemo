import sys
import uuid
import traceback
import shlex
from typing import List, Optional, Dict, Any, Tuple, Literal
from dataclasses import dataclass, field
import os
import sqlite3 # Keep for potential type hints or errors if needed

import typer
from typing_extensions import Annotated
from rich.console import Console, Group
from rich.panel import Panel
from rich.markup import escape
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
import click

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver # Import for type hint

from superego_core import create_workflow, create_models
from config import CONFIG
from constitution_utils import (
    get_available_constitutions,
    get_combined_constitution_content,
    _is_valid_id_format,
    DISALLOWED_ID_CHARS,
)
from display_utils import run_graph_and_display_live, create_panel_for_message
from cli_constants import STYLES, NODE_COLORS, CONSTITUTION_SEPARATOR
import traceback # Keep for potential debugging if needed later
# ... other imports ...
from langgraph.checkpoint.base import BaseCheckpointSaver
console = Console()

@dataclass
class CliState:
    """Holds the current CLI state."""
    graph_app: Any
    checkpointer: BaseCheckpointSaver # Use BaseCheckpointSaver for type hint
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_constitution_content: str = ""
    current_constitution_ids: List[str] = field(default_factory=lambda: ["none"])
    compare_mode_active: bool = False
    compare_constitution_sets: List[List[str]] = field(default_factory=list)

def print_as(level: Literal["error", "warning", "info", "highlight"], message: str):
    """Prints a styled message."""
    style = STYLES.get(level, STYLES["default"])
    prefix = f"{level.capitalize()}: " if level in ["error", "warning"] else ""
    console.print(f"[{style}]{prefix}{escape(message)}[/{style}]")

def _build_commands_panel() -> Panel:
    """Builds the Rich Panel for displaying commands."""
    commands = [
        ("/help", "Show this help panel", ""),
        ("/threads", "List/select chat threads", ""),
        ("/history", "Show current thread history", ""),
        ("/new", "Start a new chat thread", ""),
        ("/constitutions", "List available constitutions", ""),
        (f"/use [ID|ID{CONSTITUTION_SEPARATOR}ID...]", "Set active constitution(s)", f"`/use default`, `/use default{CONSTITUTION_SEPARATOR}strict`"),
        (f"/compare <set1> [set2...]", "Compare sets on next prompt", f"`/compare none default default{CONSTITUTION_SEPARATOR}strict`"),
        ("/compare_off", "Turn off compare mode", ""),
        ("/quit | /exit", "Exit the application", ""),
        ("`/use` (no args)", "Show list & prompt for selection", "")
    ]

    max_cmd_len = max(len(cmd[0]) for cmd in commands)
    padding_space = 4
    renderables = [
        Text.assemble(
            Text(f"{cmd:<{max_cmd_len}}", style="cyan"),
            Text(f"{' ' * padding_space}{desc}", style="green"),
            (Text(f"\n{' ' * (max_cmd_len + padding_space)}{example}", style="orange1") if example else "")
        ) for cmd, desc, example in commands
    ]
    return Panel(Group(*renderables), title="Commands", border_style="blue", expand=False)

def _build_constitutions_table(include_numbers: bool = False) -> Optional[Tuple[Table, List[str]]]:
    """Builds the Rich Table for constitutions."""
    try:
        all_constitutions = get_available_constitutions()
    except Exception as e:
        print_as("error", f"Could not load constitutions: {e}")
        return None

    table = Table(show_header=True, header_style="bold magenta", expand=False)
    id_col_name = "#" if include_numbers else "ID"
    table.add_column(id_col_name, style="cyan", no_wrap=True, header_style="bold cyan")
    if include_numbers: table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Description", style="green")

    sorted_ids = sorted(k for k in all_constitutions if k != "none")
    sorted_ids.insert(0, "none") # Ensure 'none' is first if it exists

    final_sorted_ids = []
    for i, const_id in enumerate(sorted_ids):
        # Ensure 'none' is handled even if missing from files
        if const_id == "none" and "none" not in all_constitutions:
            all_constitutions["none"] = {"description": "No specific constitution applied."}

        final_sorted_ids.append(const_id)
        details = all_constitutions.get(const_id, {})
        description = details.get('description', '[i]N/A[/i]')
        if include_numbers: table.add_row(str(i + 1), const_id, description)
        else: table.add_row(const_id, description)

    return table, final_sorted_ids

def display_startup_info(state: CliState):
    """Displays the structured startup info"""
    console.print(Panel("[bold cyan]Superego Chat[/]", border_style="cyan", expand=False))
    console.print(_build_commands_panel())
    console.print(Text.from_markup(f"[dim]Tip: Combine IDs with '{CONSTITUTION_SEPARATOR}', e.g., `default{CONSTITUTION_SEPARATOR}strict`[/dim]\n"))

    console.print(Rule("Constitutions", style="green"))
    build_result = _build_constitutions_table(include_numbers=False)
    if build_result: console.print(build_result[0])
    else: console.print("[dim]Could not display constitutions.[/dim]")

    active_const_str = CONSTITUTION_SEPARATOR.join(state.current_constitution_ids)
    console.print(f"\nUsing Constitution: [bold magenta]{escape(active_const_str)}[/bold magenta]")

def _update_active_constitutions(state: CliState, selected_id_string: str, silent: bool = False):
    """Loads constitution content based on selected ID string and updates state."""
    ids_to_load_raw = [id.strip() for id in selected_id_string.split(CONSTITUTION_SEPARATOR) if id.strip()]
    if not ids_to_load_raw or ids_to_load_raw == ["none"]: ids_to_load = ["none"]
    else:
        ids_to_load = [id_val for id_val in ids_to_load_raw if id_val != "none"]
        if not ids_to_load: ids_to_load = ["none"] # Default back to none if only 'none' was filtered out

    invalid_ids = [id_val for id_val in ids_to_load if not _is_valid_id_format(id_val)]
    if invalid_ids:
        print_as("error", f"Invalid ID format: {', '.join(invalid_ids)}. Cannot use spaces or '{escape(DISALLOWED_ID_CHARS)}'.")
        if not silent: print_as("warning", f"Keeping previous: {CONSTITUTION_SEPARATOR.join(state.current_constitution_ids)}")
        return

    try:
        combined_content, loaded_ids = get_combined_constitution_content(ids_to_load)
    except Exception as e:
        print_as("error", f"Failed to load constitution content: {e}")
        if not silent: print_as("warning", f"Keeping previous: {CONSTITUTION_SEPARATOR.join(state.current_constitution_ids)}")
        return

    state.current_constitution_content = combined_content
    state.current_constitution_ids = loaded_ids

    if not silent:
        ids_str = CONSTITUTION_SEPARATOR.join(loaded_ids)
        print_as("info", f"Using constitution(s): {ids_str}")
        requested_valid_format_ids = set(id_val for id_val in ids_to_load if id_val != "none")
        missing_ids = requested_valid_format_ids - set(loaded_ids)
        if missing_ids: print_as("warning", f"Note: Constitution(s) not found/loaded: {', '.join(missing_ids)}")

        if state.compare_mode_active:
            state.compare_mode_active = False; state.compare_constitution_sets = []
            print_as("highlight", "Compare mode turned off.")

def _display_and_select_constitution(state: CliState):
    """Displays constitutions with numbers and prompts user for selection."""
    console.print(Rule("Select Constitution", style="dim"))
    build_result = _build_constitutions_table(include_numbers=True)
    if not build_result: return

    constitutions_table, id_list = build_result
    console.print(constitutions_table)

    prompt = (f"Select # (1-{len(id_list)}) or enter ID name(s) "
              f"(e.g., 'dft' or 'dft{CONSTITUTION_SEPARATOR}strict', Enter=cancel): ")
    choice_str = console.input(prompt).strip()
    if not choice_str: print_as("info", "Selection cancelled."); return

    selected_id_string = None
    try:
        choice_idx = int(choice_str) - 1
        if 0 <= choice_idx < len(id_list): selected_id_string = id_list[choice_idx]
        else: print_as("error", "Invalid selection number."); return
    except ValueError: selected_id_string = choice_str

    if selected_id_string:
         _update_active_constitutions(state, selected_id_string, silent=False)

def _display_history(thread_id: str, graph_app: Any):
    """Shows chat history."""
    console.print(Rule(f"History: {thread_id}", style="dim"))
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state_data = graph_app.get_state(config)
        messages = state_data.values.get('messages', []) if state_data and hasattr(state_data, 'values') else []
    except Exception as e:
        # Log minimal error if state cannot be retrieved
        print_as("warning", f"Could not retrieve history state: {e}")
        messages = []

    renderables = [f"[{STYLES['user']}]User:[/ {STYLES['user']}] {escape(msg.content)}" if isinstance(msg, HumanMessage) else create_panel_for_message(msg) for msg in messages]
    valid_renderables = [r for r in renderables if r is not None]
    console.print(Group(*valid_renderables) if valid_renderables else "[dim]No messages.[/dim]")
    console.print(Rule("End History", style="dim"))

# Accept the persistent checkpointer instance

# Accept the persistent checkpointer instance

def _list_and_select_thread(checkpointer: BaseCheckpointSaver) -> Optional[str]:
    """Lists threads and prompts for selection, safely handling different checkpoint types."""
    console.print(Rule("Available Threads", style="dim"))
    threads = []
    processed_thread_ids = set()

    try:
        if not checkpointer:
             # This is a genuine error state if the checkpointer wasn't passed correctly
             raise ValueError("Checkpointer object is None.")

        # List recent checkpoints (config={} means no filter based on config content)
        saved_checkpoints = checkpointer.list(config={}, limit=100)

        # Iterate and safely extract thread_ids from relevant checkpoints
        for cpt in saved_checkpoints:
            config_dict = getattr(cpt, 'config', None)
            if isinstance(config_dict, dict):
                # Safely get 'configurable', returns None if key missing
                configurable_dict = config_dict.get('configurable')
                if isinstance(configurable_dict, dict):
                    # Safely get 'thread_id', returns None if key missing
                    thread_id = configurable_dict.get('thread_id')
                    # Process only if thread_id is a non-empty string
                    if thread_id and isinstance(thread_id, str):
                         processed_thread_ids.add(thread_id)
            # Checkpoints without the expected structure are implicitly skipped here

        if processed_thread_ids:
            # Sort unique IDs, filter compares
            unique_threads = sorted(list(processed_thread_ids), reverse=True)
            threads = [t for t in unique_threads if not t.endswith("_compare")]

    except Exception as e:
        # Catch significant errors during the overall list operation or checkpointer access
        print_as("error", f"Could not retrieve threads: {e}")
        # traceback.print_exc() # Uncomment only if deep debugging is needed
        return None

    # --- Display Table and Prompt ---
    if not threads:
        console.print("[dim]No threads found.[/dim]")
        return None

    table = Table(title="Select Thread")
    table.add_column("#", style="cyan"); table.add_column("Thread ID", style="green")
    for i, thread_id in enumerate(threads):
        table.add_row(str(i + 1), thread_id)
    console.print(table)

    try:
        choice_str = console.input(f"Select # (1-{len(threads)}, Enter=cancel): ").strip()
        if not choice_str: console.print_as("info", "Selection cancelled."); return None
        choice_idx = int(choice_str) - 1
        if 0 <= choice_idx < len(threads):
            return threads[choice_idx]
        else:
            print_as("error", "Invalid selection.")
    except ValueError:
        print_as("error", "Invalid number.")
    except Exception as e:
        print_as("error", f"An error occurred during thread selection: {e}")
    return None



cli_app = typer.Typer(help="Superego Chat CLI.", add_completion=False, no_args_is_help=False)

@cli_app.command()
def help(ctx: typer.Context):
    display_startup_info(ctx.obj)

@cli_app.command()
def history(ctx: typer.Context):
    _display_history(ctx.obj.thread_id, ctx.obj.graph_app)

@cli_app.command()
def threads(ctx: typer.Context):
    state: CliState = ctx.obj
    selected_thread_id = _list_and_select_thread(state.checkpointer) # Pass instance
    if selected_thread_id:
        state.thread_id = selected_thread_id
        print_as("info", f"Switched to thread: {state.thread_id}")
        _display_history(state.thread_id, state.graph_app)

@cli_app.command()
def new(ctx: typer.Context):
    state: CliState = ctx.obj
    state.thread_id = str(uuid.uuid4())
    print_as("info", f"Started new thread: {state.thread_id}")

@cli_app.command()
def constitutions(ctx: typer.Context):
    console.print(Rule("Constitutions", style="green"))
    build_result = _build_constitutions_table(include_numbers=False)
    if build_result: console.print(build_result[0])
    else: console.print("[dim]Could not display constitutions.[/dim]")

@cli_app.command(name="use")
def use_constitution(
    ctx: typer.Context,
    ids: Annotated[Optional[str], typer.Argument(help=f"ID(s) (e.g., 'dft' or 'dft{CONSTITUTION_SEPARATOR}strict').")] = None
):
    if ids is None: _display_and_select_constitution(ctx.obj)
    else: _update_active_constitutions(ctx.obj, ids, silent=False)

@cli_app.command()
def compare(
    ctx: typer.Context,
    sets_input: Annotated[List[str], typer.Argument(help=f"Space-separated sets (e.g., none c1 c1{CONSTITUTION_SEPARATOR}c2)")]
):
    state: CliState = ctx.obj
    parsed_sets: List[List[str]] = []
    valid_format_overall = True

    if not sets_input: print_as("error", "No sets provided for /compare."); valid_format_overall = False
    else:
        for set_str in sets_input:
            ids_in_set_raw = [id.strip() for id in set_str.split(CONSTITUTION_SEPARATOR) if id.strip()]
            if not ids_in_set_raw: print_as("error", f"Empty set or invalid separator use near '{set_str}'."); valid_format_overall = False; break

            ids_in_set = ["none"] if ids_in_set_raw == ["none"] else \
                         [id_val for id_val in ids_in_set_raw if id_val != "none"]
            if not ids_in_set and "none" in ids_in_set_raw: ids_in_set = ["none"]
            elif not ids_in_set: print_as("error", f"Set '{set_str}' resulted in no valid IDs."); valid_format_overall = False; break

            if not all(_is_valid_id_format(id_val) for id_val in ids_in_set): print_as("error", f"Invalid ID format in set '{set_str}'."); valid_format_overall = False; break

            parsed_sets.append(ids_in_set)

    state.compare_mode_active = valid_format_overall
    if valid_format_overall:
        state.compare_constitution_sets = parsed_sets
        sets_display = [CONSTITUTION_SEPARATOR.join(s) if s != ["none"] else "none" for s in parsed_sets]
        print_as("highlight", f"Compare mode active: {', '.join(sets_display)}")
    else: state.compare_constitution_sets = []; print_as("warning", "Compare mode NOT activated.")

def _try_run_command(line: str, state: CliState, typer_click_group: click.Command) -> bool:
    """Parses and executes slash commands. Returns False if REPL should exit."""
    try:
        args = shlex.split(line, posix=True)
        if not args: return True
        cmd_name = args[0].lower()
        cmd_args = args[1:]
    except ValueError as e: print_as("error", f"Argument parsing error: {e}"); return True

    if cmd_name in ['quit', 'exit']: return False
    if cmd_name == 'compare_off':
        if state.compare_mode_active:
            state.compare_mode_active = False; state.compare_constitution_sets = []
            print_as("highlight", "Compare mode turned off.")
        return True

    subcommand = typer_click_group.get_command(ctx=None, cmd_name=cmd_name)
    if subcommand:
        try:
            subcommand.main(args=cmd_args, prog_name=cmd_name, obj=state, standalone_mode=False)
        except click.exceptions.ClickException as e: e.show()
        except Exception as e:
            print_as("error", f"Error executing '/{cmd_name}': {e}")
            # traceback.print_exc() # Uncomment for debug
    else: print_as("error", f"Unknown command: /{cmd_name}. Try /help.")

    return True

def run_main_loop():
    """Initializes and runs the main Read-Eval-Print Loop."""
    state = None
    try:
        superego_model, inner_model = create_models()
        graph_app, checkpointer = create_workflow(superego_model=superego_model, inner_model=inner_model)
    except Exception as e: print_as("error", f"Initialization failed: {e}"); traceback.print_exc(); sys.exit(1)

    try:
        state = CliState(graph_app=graph_app, checkpointer=checkpointer) # Store instance
        typer_click_group = typer.main.get_command(cli_app)
        _update_active_constitutions(state, "none", silent=True)
        display_startup_info(state)

        while True:
            try:
                prompt_prefix = "[yellow bold](Compare Mode)[/] " if state.compare_mode_active else ""
                full_prompt = f"\n{prompt_prefix}[{STYLES['user']}]User:[/ {STYLES['user']}] "

                line = console.input(full_prompt)
                if not line.strip(): continue

                if line.startswith('/'):
                    if not _try_run_command(line[1:].strip(), state, typer_click_group): break
                    continue

                messages = [HumanMessage(content=line)]

                if state.compare_mode_active:
                    print_as("highlight", f"Running Compare Mode ({len(state.compare_constitution_sets)} set(s))...")
                    original_thread_id = state.thread_id
                    original_const_ids = state.current_constitution_ids[:]
                    compare_run_uuid = str(uuid.uuid4())[:8]

                    for i, const_set_ids in enumerate(state.compare_constitution_sets):
                        set_name = CONSTITUTION_SEPARATOR.join(const_set_ids) if const_set_ids != ["none"] else "none"
                        title = f"Compare Run {i+1}/{len(state.compare_constitution_sets)}: [cyan]{set_name}[/cyan]"
                        state.thread_id = f"{original_thread_id}_compare_{compare_run_uuid}_{i+1}"

                        content_for_run, loaded_ids_for_run = get_combined_constitution_content(const_set_ids)
                        requested_set = set(id for id in const_set_ids if id != "none")
                        missing_in_run = requested_set - set(loaded_ids_for_run)
                        if missing_in_run: print_as("warning", f"Run '{set_name}': Cannot load {', '.join(missing_in_run)}. Running without.")

                        # Let errors propagate from here in demo mode
                        run_graph_and_display_live(console, state, content_for_run, messages, title)

                    state.thread_id = original_thread_id
                    state.compare_mode_active = False; state.compare_constitution_sets = []
                    _update_active_constitutions(state, CONSTITUTION_SEPARATOR.join(original_const_ids), silent=True)
                    print_as("highlight", f"Compare finished. Restored constitution: {CONSTITUTION_SEPARATOR.join(state.current_constitution_ids)}")

                else:
                    # Let errors propagate from here in demo mode
                    run_graph_and_display_live(console, state, state.current_constitution_content, messages)

            except (KeyboardInterrupt, EOFError): print_as("info", "\nExiting."); break
            # Catch errors within the loop to attempt continuation
            except Exception as e: print_as("error", f"An error occurred: {e}"); traceback.print_exc(); print_as("warning", "Attempting to continue...")

    # Use finally to ensure DB connection is closed on exit
    finally:
        if state and state.checkpointer and hasattr(state.checkpointer, 'conn') and state.checkpointer.conn:
            try:
                print_as("info", "Closing database connection...")
                state.checkpointer.conn.close()
            except Exception as e:
                print_as("warning", f"Error closing checkpointer connection: {e}")
        else:
            # Ensure a general exit message is always printed if cleanup isn't needed/possible
            print_as("info", "Exiting application.")


if __name__ == "__main__":
    try:
        # Check import early
        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.checkpoint.base import BaseCheckpointSaver
    except ImportError as e:
        print(f"[bold red]Error: Failed to import langgraph components: {e}. Is langgraph installed correctly?[/]", file=sys.stderr)
        sys.exit(1)

    try:
        run_main_loop()
    except Exception as e:
        # Catch potential critical errors during the main loop setup that weren't caught inside
        print(f"\n[bold red]Critical error during execution: {e}[/]", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
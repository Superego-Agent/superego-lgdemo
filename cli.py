"""CLI interface for the Superego Chat System"""
import os
import typer
from typing import Optional, Dict, Any
from colorama import init
from rich.console import Console
from rich.panel import Panel

from superego_core import (
    create_models, 
    create_workflow, 
    get_or_create_session,
    add_user_message,
    run_session
)

from constitution_cli import app as constitution_app, interactive_menu as constitution_menu

init(autoreset=True)
console = Console()

app = typer.Typer(help="Superego Chat System CLI", no_args_is_help=False)
app.add_typer(constitution_app, name="constitution", help="Manage constitutions")

CLI_CONFIG = {
    "debug": False,
    "show_routing": True,
    "editor": os.environ.get("EDITOR", "nano"),
}

def visualize_workflow():
    workflow_text = """
START
  ↓
SUPEREGO (Moderation)
  ↓
TOOLS (ALLOW/BLOCK Decision)
  ↓
Should Continue? ─── Yes ──→ INNER AGENT → END
      │
      No
      ↓
     END
"""
    console.print(Panel(
        workflow_text,
        title="[bold cyan]WORKFLOW VISUALIZATION[/bold cyan]",
        border_style="cyan",
        expand=False
    ))

class MessageRenderer:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.superego_buffer = ""
        self.inner_buffer = ""
        self.message_count = 0
        self.superego_started = False
        self.inner_started = False
    
    def end_current_panel(self):
        if self.superego_started:
            console.print("\n╰─────────────────────────────────────────────────────────────────────────╯")
            self.superego_started = False
        elif self.inner_started:
            console.print("\n╰─────────────────────────────────────────────────────────────────────────╯")
            self.inner_started = False
            
    def render_agent_message(self, node_name, content):
        if node_name == "superego":
            self._render_superego_message(content)
        elif node_name == "inner_agent":
            self._render_inner_message(content)
    
    def _render_superego_message(self, content):
        if self.inner_started and not self.superego_started:
            print("\n")
            
        if not self.superego_started:
            print("\n")
            console.print("╭─────────────────────────── [yellow bold]Superego[/yellow bold] ───────────────────────────╮")
            self.superego_started = True
            self.message_count += 1
            if self.inner_started:
                self.inner_started = False
        
        self.superego_buffer += content
        print(content, end="", flush=True)
    
    def _render_inner_message(self, content):
        if self.superego_started and not self.inner_started:
            console.print("╰─────────────────────────────────────────────────────────────────────────╯\n")
            self.superego_started = False
            
        if not self.inner_started:
            console.print("╭─────────────────────────── [green bold]Claude[/green bold] ───────────────────────────╮")
            self.inner_started = True
            self.message_count += 1
            
        self.inner_buffer += content
        print(content, end="", flush=True)
    
    def render_tool_call(self, node_name, tool_name, tool_input="", tool_result=""):
        self.end_current_panel()
        
        agent_name = "Superego" if node_name == "tools" else "Claude"
        agent_color = "yellow" if agent_name == "Superego" else "green"
        
        console.print(f"╭─────────────────────────── [magenta bold]Tool Call[/magenta bold] ───────────────────────────╮")
        console.print(f"  [{agent_color}]{agent_name}[/{agent_color}] called: [bold magenta]{tool_name}[/bold magenta]")
        
        if tool_input:
            console.print(f"  [bold]Input:[/bold] {tool_input}")
        if tool_result:
            console.print(f"  [bold]Result:[/bold] {tool_result}")
            
        console.print("╰─────────────────────────────────────────────────────────────────────────╯")

def render_stream_event(event: Dict[str, Any], renderer: MessageRenderer) -> None:
    stream_type = event.get("stream_type")
    node_name = event.get("node_name")
    
    if stream_type == "messages" and "content" in event:
        renderer.render_agent_message(node_name, event["content"])
    
    elif stream_type == "values":
        if CLI_CONFIG["debug"]:
            if CLI_CONFIG["show_routing"] and node_name:
                console.print(f"\n[dim blue][ROUTING] → {node_name.upper()}[/dim blue]")
            console.print(f"\n[dim cyan][DEBUG] Event: {event}[/dim cyan]")
        
        tool_name = None
        tool_input = ""
        tool_result = ""
        
        if "tool_name" in event:
            tool_name = event["tool_name"]
            tool_input = event.get("tool_input", "")
            tool_result = event.get("tool_result", "")
        elif "state" in event and isinstance(event["state"], dict) and "tool_name" in event["state"]:
            tool_name = event["state"]["tool_name"]
            tool_input = event["state"].get("tool_input", "")
            tool_result = event["state"].get("tool_result", "")
            
        if tool_name:
            renderer.render_tool_call(node_name, tool_name, tool_input, tool_result)

@app.command("chat")
def chat_loop(
    session_id: Optional[str] = typer.Option(None, "--session", "-s", help="Session ID to resume"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output")
):
    """Run the interactive chat loop with the Superego system."""
    CLI_CONFIG["debug"] = debug
    
    superego_model, inner_model = create_models()
    app = create_workflow(superego_model, inner_model)
    session_id = get_or_create_session(session_id)
    
    console.print(Panel("[bold cyan]SUPEREGO CHAT SYSTEM[/bold cyan]", border_style="cyan"))
    console.print(f"Session: [blue]{session_id}[/blue]")
    
    if CLI_CONFIG["debug"]:
        console.print("[cyan][DEBUG MODE ACTIVE][/cyan]")
    
    console.print("Type 'exit' or 'quit' to end.\n")
    
    if CLI_CONFIG["show_routing"]:
        visualize_workflow()
    
    renderer = MessageRenderer()
    
    while True:
        renderer.reset()
        
        console.print("[bold blue]User:[/bold blue]", end=" ")
        user_input = input()
        if user_input.lower() in ["exit", "quit"]:
            console.print("[cyan]\nThank you for using Superego Chat. Goodbye![/cyan]")
            break
            
        add_user_message(session_id, user_input)
        
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"]:
            console.print("[dim blue][ROUTING] STARTING WORKFLOW[/dim blue]")
            console.print("[dim blue][ROUTING] → START[/dim blue]")
        
        for event in run_session(session_id, app):
            render_stream_event(event, renderer)
        
        renderer.end_current_panel()
        
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"]:
            console.print("[dim blue][ROUTING] → END OF WORKFLOW[/dim blue]")
        
        print()

@app.command("menu")
def main_menu():
    """Show the main menu for the application."""
    menu_options = {
        1: {"label": "Start Chat", "action": lambda: chat_loop(debug=CLI_CONFIG["debug"])},
        2: {"label": "Manage Constitutions", "action": constitution_menu},
        3: {"label": "Exit", "action": None},
    }
    
    while True:
        console.print(Panel("[bold cyan]SUPEREGO CHAT SYSTEM[/bold cyan]", border_style="cyan"))
        console.print("[cyan]MAIN MENU:[/cyan]")
        
        for key, option in menu_options.items():
            console.print(f"{key}. {option['label']}")
        
        choice = typer.prompt("\nEnter your choice", type=int, default=1)
        
        if choice in menu_options:
            if choice == 3:
                console.print("[cyan]\nThank you for using Superego Chat. Goodbye![/cyan]")
                break
            menu_options[choice]["action"]()
        else:
            console.print("[red]Invalid choice. Please enter a number from 1-3.[/red]")

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug output"),
):
    """Main entry point for the Superego Chat CLI."""
    CLI_CONFIG["debug"] = debug
    
    if os.name == "nt":
        os.system("color")
    
    if ctx.invoked_subcommand is None:
        main_menu()

if __name__ == "__main__":
    app()

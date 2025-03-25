"""CLI interface for the Superego Chat System"""
import os
import json
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
    "divider": "─" * 40,
    "always_show_tools": True  # Always show tool calls regardless of debug mode
}

def visualize_workflow():
    workflow_text = """
START
  ↓
SUPEREGO (Moderation)
  ↓
TOOLS (Superego makes ALLOW/BLOCK Decision)
  ↓
Should Continue? ─── Yes ──→ INNER_AGENT ────→ END
      │                          │
      │                          │ (May use tools)
      │                          ↓
      │                        TOOLS
      │                          │
      │                          ↑
      No                         │
      ↓                          │
     END                         │
"""

    console.print(Panel(
        workflow_text,
        title="[bold cyan]WORKFLOW[/bold cyan]",
        border_style="cyan",
        expand=False
    ))


# Simplified color mapping
NODE_COLORS = {
    "superego": "yellow",
    "inner_agent": "green",
    "tools": "magenta",
    "inner_tools": "magenta"
}

class MessageRenderer:
    """Simplified message renderer following Langgraph example style"""
    def __init__(self):
        self.current_node = None

    def render_agent_message(self, node_name, content):
        """Render agent message with custom header"""
        if node_name != self.current_node:
            # New node - print header
            if node_name in NODE_COLORS:
                color = NODE_COLORS[node_name]
                console.print(f"\n[{color}]-------- {node_name.title()}:[/{color}]")
            self.current_node = node_name
            
        # Stream content with flush
        print(content, end='', flush=True)
    
    def render_tool_call(self, node_name, tool_name, tool_input="", tool_result="", agent=None):
        """Render tool call with tool-specific formatting"""
        agent = agent or node_name
        
        # Show tool call inline with agent message
        if tool_input:
            console.print(f"\n[dim]Calling tool: {tool_name}[/dim]")
            console.print(f"[dim]Input: {tool_input}[/dim]")

def render_stream_event(event: Dict[str, Any], renderer: MessageRenderer) -> None:
    stream_type = event.get("stream_type")
    node_name = event.get("node_name")
    
    # Debug logging
    if CLI_CONFIG["debug"]:
        console.print(f"\n[dim cyan][DEBUG] Event: {event}[/dim cyan]")
    
    # Handle tool events
    if "tool_name" in event:
        tool_name = event["tool_name"].upper()
        tool_input = event.get("tool_input", "")
        tool_result = event.get("tool_result", "")
        agent = event.get("agent", node_name)  # Default to node_name if agent not specified
        
        # Format tool input if it's a dict
        if isinstance(tool_input, dict):
            tool_input = json.dumps(tool_input, indent=2)
        
        renderer.render_tool_call(node_name, tool_name, tool_input, tool_result, agent)
        return
        
    # Handle message events
    if stream_type == "messages" and "content" in event:
        content = event["content"]
        if content and not content.isspace():
            if node_name == "tools" and content == "true":
                return  # Skip tool messages
                
            if event.get("end_of_message", False):
                content += '\n'
            
            renderer.render_agent_message(node_name, content)
    
    # Show routing info in debug mode
    elif stream_type == "values" and CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"] and node_name:
        console.print(f"\n[dim blue][ROUTING] → {node_name.upper()}[/dim blue]")

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
        
        console.print("\n\n[bold blue]User:[/bold blue]", end=" ")
        user_input = input()
        if user_input.lower() in ["exit", "quit"]:
            console.print("[cyan]Exiting Flow.[/cyan]")
            break
            
        add_user_message(session_id, user_input)
        
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"]:
            console.print("[dim blue][ROUTING] → START[/dim blue]")
        
        for event in run_session(session_id, app):
            render_stream_event(event, renderer)
        
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

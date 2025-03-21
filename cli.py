"""CLI interface for the Superego Chat System"""
import os
import typer
from typing import Optional, Dict, Any
from colorama import init
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

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
TOOLS (ALLOW/BLOCK Decision)
  ↓
Should Continue? ─── Yes ──→ inner_agent → END
      │
      No
      ↓
     END
"""
    console.print(Panel(
        workflow_text,
        title="[bold cyan]WORKFLOW[/bold cyan]",
        border_style="cyan",
        expand=False
    ))

class MessageBox:
    """A streamlined component for rendering boxed messages in the CLI."""
    BOX_WIDTH = 75
    BOX_TOP = "╭" + "─" * (BOX_WIDTH - 2) + "╮"
    BOX_BOTTOM = "╰" + "─" * (BOX_WIDTH - 2) + "╯"
    
    def __init__(self, console, title=None, title_style=None):
        self.console = console
        self.title = title
        self.title_style = title_style
    
    def render_box(self, content="", add_newline=True):
        """Render a complete message box with optional title and content"""
        if add_newline:
            print("\n")
            
        if self.title:
            title_display = f" [{self.title_style}]{self.title}[/{self.title_style}] "
            padding = "─" * ((self.BOX_WIDTH - len(self.title) - 4) // 2)
            header = f"╭{padding}{title_display}{padding}╮"
            if len(Text.from_markup(header).plain) < self.BOX_WIDTH:
                header = header[:-1] + "─╮"
            self.console.print(header)
        else:
            self.console.print(self.BOX_TOP)
            
        if content:
            # Use console.print for rich text formatting
            self.console.print(content)
            self.console.print(self.BOX_BOTTOM)
        if add_newline:
            print()
    
    def render_labeled_content(self, label, content, label_style="bold"):
        """Render content with a styled label"""
        self.console.print(f"  [{label_style}]{label}:[/{label_style}] {content}")

class MessageRenderer:
    """Manages rendering of different message types"""
    def __init__(self):
        self.reset()
        
    def reset(self):
        """Reset renderer state between messages"""
        self.current_node = None
        self.current_content = ""
        
    def render_agent_message(self, node_name, content):
        # If switching to a different agent, render current content first
        if self.current_node != node_name and self.current_content:
            self._render_current_content()
            
        self.current_node = node_name
        self.current_content += content
    
    def _render_current_content(self):
        """Render accumulated content for current node"""
        if not self.current_content:
            return
            
        title = "Superego" if self.current_node == "superego" else "inner_agent"
        style = "yellow bold" if self.current_node == "superego" else "green bold"
        
        box = MessageBox(console, title, style)
        box.render_box(self.current_content, add_newline=True)
        
        self.current_content = ""
        
    def render_tool_call(self, node_name, tool_name, tool_input="", tool_result=""):
        # Render any pending agent message first
        if self.current_content:
            self._render_current_content()
        
        box = MessageBox(console, "Tool", "magenta bold")
        # Format tool name with proper indentation and styling
        content = f"  [bold magenta]{tool_name}[/bold magenta]"
        
        # Add input/result with proper formatting
        if tool_input:
            content += f"\n  [bold]Input:[/bold] {tool_input}"
        if tool_result:
            content += f"\n  [bold]Result:[/bold] {tool_result}"
            
        box.render_box(content)
    
    def end_current_panel(self):
        """Render any remaining content"""
        if self.current_content:
            self._render_current_content()

def render_stream_event(event: Dict[str, Any], renderer: MessageRenderer) -> None:
    stream_type = event.get("stream_type")
    node_name = event.get("node_name")
    
    if stream_type == "messages" and "content" in event:
        content = event["content"]
        if content and not content.isspace():
            # Check if this is the end of a complete message
            is_end = event.get("end_of_message", False)
            if is_end and not content.endswith('\n'):
                content += '\n'
            
            # Handle ALLOW/BLOCK messages from tools node as tool calls
            if node_name == "tools":
                if "ALLOWED:" in content:
                    renderer.render_tool_call(node_name, "ALLOW", content.replace("ALLOWED:", "").strip())
                elif "BLOCKED:" in content:
                    renderer.render_tool_call(node_name, "BLOCK", content.replace("BLOCKED:", "").strip())
            else:
                renderer.render_agent_message(node_name, content)
    
    elif stream_type == "values":
        # Show routing info only in debug mode
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"] and node_name:
            console.print(f"\n[dim blue][ROUTING] → {node_name.upper()}[/dim blue]")
        
        # Always log full events in debug mode
        if CLI_CONFIG["debug"]:
            console.print(f"\n[dim cyan][DEBUG] Event: {event}[/dim cyan]")
        
        # Extract tool information
        tool_name = None
        tool_input = ""
        tool_result = ""
        
        # Handle tool calls from the tools node (constitution checks)
        if node_name == "tools":
            if "messages" in event:
                for msg in event["messages"]:
                    if isinstance(msg, dict) and "content" in msg:
                        content = msg["content"]
                        if "ALLOWED:" in content:
                            tool_name = "ALLOW"
                            tool_input = content.replace("ALLOWED:", "").strip()
                        elif "BLOCKED:" in content:
                            tool_name = "BLOCK"
                            tool_input = content.replace("BLOCKED:", "").strip()
        # Handle other tool calls
        elif "tool_name" in event:
            tool_name = event["tool_name"]
            tool_input = event.get("tool_input", "")
            tool_result = event.get("tool_result", "")
        elif "state" in event and isinstance(event["state"], dict) and "tool_name" in event["state"]:
            tool_name = event["state"]["tool_name"]
            tool_input = event["state"].get("tool_input", "")
            tool_result = event["state"].get("tool_result", "")
        elif "additional_kwargs" in event and "tool_calls" in event["additional_kwargs"]:
            for tool_call in event["additional_kwargs"]["tool_calls"]:
                if isinstance(tool_call, dict) and "function" in tool_call:
                    tool_name = tool_call["function"].get("name")
                    tool_input = str(tool_call["function"].get("arguments", ""))
        
        # Always render the tool call if we found a tool_name
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

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

class MessageBox:
    """A reusable component for rendering boxed messages in the CLI.
    
    This class encapsulates the creation, content management, and closing of
    message boxes with consistent styling, eliminating code duplication.
    """
    BOX_WIDTH = 75
    BOX_TOP = "╭" + "─" * (BOX_WIDTH - 2) + "╮"
    BOX_BOTTOM = "╰" + "─" * (BOX_WIDTH - 2) + "╯"
    
    def __init__(self, console, title=None, title_style=None):
        """
        Args:
            console: Rich console instance for output
            title: Optional title for the message box
            title_style: Rich text style for the title
        """
        self.console = console
        self.title = title
        self.title_style = title_style
        self.content_buffer = ""
        self.is_open = False
    
    def open(self, add_newline=True):
        """Open a new message box with styled title"""
        if self.is_open:
            return
            
        if add_newline:
            print("\n")
            
        if self.title:
            # Create centered title with styling
            title_display = f" [{self.title_style}]{self.title}[/{self.title_style}] "
            padding = "─" * ((self.BOX_WIDTH - len(self.title) - 4) // 2)
            header = f"╭{padding}{title_display}{padding}╮"
            # Ensure the header is exactly BOX_WIDTH chars by adjusting right padding
            if len(Text.from_markup(header).plain) < self.BOX_WIDTH:
                header = header[:-1] + "─╮"
            self.console.print(header)
        else:
            self.console.print(self.BOX_TOP)
            
        self.is_open = True
    
    def add_content(self, content, end="\n"):
        """Add content to the message box"""
        if not self.is_open:
            self.open()
            
        self.content_buffer += content
        print(content, end=end, flush=True)
    
    def add_labeled_content(self, label, content, label_style="bold"):
        """Add content with a styled label"""
        if not self.is_open:
            self.open()
            
        self.console.print(f"  [{label_style}]{label}:[/{label_style}] {content}")
    
    def close(self, add_newline=True):
        """Close the message box"""
        if not self.is_open:
            return
            
        self.console.print(self.BOX_BOTTOM)
        if add_newline:
            print()
            
        self.is_open = False
        return self.content_buffer

class MessageRenderer:
    """Manages rendering of different message types using the MessageBox abstraction"""
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.superego_buffer = ""
        self.inner_buffer = ""
        self.message_count = 0
        self.current_box = None
    
    def end_current_panel(self):
        if self.current_box and self.current_box.is_open:
            self.current_box.close()
            self.current_box = None
            
    def render_agent_message(self, node_name, content):
        if node_name == "superego":
            if self.current_box and self.current_box.title != "Superego":
                self.end_current_panel()
                
            if not self.current_box or not self.current_box.is_open:
                self.current_box = MessageBox(console, "Superego", "yellow bold")
                self.current_box.open()
                self.message_count += 1
                
            self.superego_buffer += content
            self.current_box.add_content(content, end="")
            
        elif node_name == "inner_agent":
            if self.current_box and self.current_box.title != "Claude":
                self.end_current_panel()
                
            if not self.current_box or not self.current_box.is_open:
                self.current_box = MessageBox(console, "Claude", "green bold")
                self.current_box.open()
                self.message_count += 1
                
            self.inner_buffer += content
            self.current_box.add_content(content, end="")
    
    def render_tool_call(self, node_name, tool_name, tool_input="", tool_result=""):
        self.end_current_panel()
        
        agent_name = "Superego" if node_name == "tools" else "Claude"
        agent_color = "yellow" if agent_name == "Superego" else "green"
        
        tool_box = MessageBox(console, "Tool Call", "magenta bold")
        tool_box.open()
        
        # Add agent and tool information
        tool_box.add_content(f"  [{agent_color}]{agent_name}[/{agent_color}] called: [bold magenta]{tool_name}[/bold magenta]")
        
        # Add input and result if available
        if tool_input:
            tool_box.add_labeled_content("Input", tool_input)
        if tool_result:
            tool_box.add_labeled_content("Result", tool_result)
            
        tool_box.close()

def render_stream_event(event: Dict[str, Any], renderer: MessageRenderer) -> None:
    stream_type = event.get("stream_type")
    node_name = event.get("node_name")
    
    if stream_type == "messages" and "content" in event:
        renderer.render_agent_message(node_name, event["content"])
    
    elif stream_type == "values":
        # Show routing info only in debug mode
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"] and node_name:
            console.print(f"\n[dim blue][ROUTING] → {node_name.upper()}[/dim blue]")
        
        # Always log full events in debug mode
        if CLI_CONFIG["debug"]:
            console.print(f"\n[dim cyan][DEBUG] Event: {event}[/dim cyan]")
        
        # Extract tool information - always attempt to do this regardless of debug mode
        tool_name = None
        tool_input = ""
        tool_result = ""
        
        # Try different ways to extract tool information
        if "tool_name" in event:
            tool_name = event["tool_name"]
            tool_input = event.get("tool_input", "")
            tool_result = event.get("tool_result", "")
        elif "state" in event and isinstance(event["state"], dict) and "tool_name" in event["state"]:
            tool_name = event["state"]["tool_name"]
            tool_input = event["state"].get("tool_input", "")
            tool_result = event["state"].get("tool_result", "")
        # Additional extraction for tool-call specific content
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

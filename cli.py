"""CLI interface for the Superego Chat System"""
import os
import json
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

class MessageBox:
    """A streamlined component for rendering boxed messages in the CLI."""
    BOX_WIDTH = 75
    def __init__(self, console, title=None, title_style=None):
        self.console = console
        self.title = title
        self.style = title_style.replace(" bold", "") if title_style else None
    
    def render_box(self, content="", add_newline=True):
        """Render a complete message box with optional title and content"""
        if add_newline:
            print()
            
        # Create borders with color
        border_color = f"[{self.style}]" if self.style else ""
        border_reset = "[/]" if self.style else ""
        box_top = f"{border_color}╭{'─' * (self.BOX_WIDTH - 2)}╮{border_reset}"
        box_bottom = f"{border_color}╰{'─' * (self.BOX_WIDTH - 2)}╯{border_reset}"
            
        if self.title:
            title_display = f" {self.title} "
            padding = "─" * ((self.BOX_WIDTH - len(self.title) - 4) // 2)
            header = f"{border_color}╭{padding}{title_display}{padding}╮{border_reset}"
            if len(Text.from_markup(header).plain) < self.BOX_WIDTH:
                header = f"{border_color}╭{padding}{title_display}{padding}─╮{border_reset}"
            self.console.print(header)
        else:
            self.console.print(box_top)
            
        if content:
            # Print content and ensure it ends with a newline
            if not content.endswith('\n'):
                content += '\n'
            print(content, end='', flush=True)
            
            # Print bottom border
            self.console.print(box_bottom)
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
        # If switching to a different agent, end current box
        if self.current_node != node_name:
            if self.current_node:
                # Add newline before bottom border
                print()
                # Print bottom border for previous box
                style = "yellow" if self.current_node == "superego" else "green"
                border_color = f"[{style}]"
                border_reset = "[/]"
                box_bottom = f"{border_color}╰{'─' * (MessageBox.BOX_WIDTH - 2)}╯{border_reset}"
                console.print(box_bottom)
                print("\n")  # Extra newline after box
            
            # Print top border and title for new box
            self.current_node = node_name
            title = "Superego" if node_name == "superego" else "inner_agent"
            style = "yellow" if node_name == "superego" else "green"
            border_color = f"[{style}]"
            border_reset = "[/]"
            
            title_display = f" {title} "
            padding = "─" * ((MessageBox.BOX_WIDTH - len(title) - 4) // 2)
            header = f"{border_color}╭{padding}{title_display}{padding}╮{border_reset}"
            if len(Text.from_markup(header).plain) < MessageBox.BOX_WIDTH:
                header = f"{border_color}╭{padding}{title_display}{padding}─╮{border_reset}"
            
            console.print(header)
            print()  # Newline after top border
        
        # Print content immediately
        print(content, end='', flush=True)
    
    def end_current_panel(self):
        """End the current message box if one is open"""
        if self.current_node:
            # Add newline before bottom border
            print()
            style = "yellow" if self.current_node == "superego" else "green"
            border_color = f"[{style}]"
            border_reset = "[/]"
            box_bottom = f"{border_color}╰{'─' * (MessageBox.BOX_WIDTH - 2)}╯{border_reset}"
            console.print(box_bottom)
            print("\n")  # Extra newline after box
            self.current_node = None
        
    def render_tool_call(self, node_name, tool_name, tool_input="", tool_result="", agent=None):
        # End any current message box
        if self.current_node:
            self.end_current_panel()
        
        # Print tool box with magenta borders
        border_color = "[magenta]"
        border_reset = "[/]"
        
        # Print top border with title
        agent_prefix = f"{agent} " if agent else ""
        title_display = f" {agent_prefix}Tool "
        padding = "─" * ((MessageBox.BOX_WIDTH - len(title_display) - 2) // 2)
        header = f"{border_color}╭{padding}{title_display}{padding}╮{border_reset}"
        if len(Text.from_markup(header).plain) < MessageBox.BOX_WIDTH:
            header = f"{border_color}╭{padding}{title_display}{padding}─╮{border_reset}"
        
        print("\n")  # Extra newline before box
        console.print(header)
        
        # Print content
        print()  # Newline after top border
        print(f"  {tool_name}")
        if tool_input:
            print(f"  Input: {tool_input}")
        if tool_result:
            print(f"  Result: {tool_result}")
        
        # Print bottom border
        box_bottom = f"{border_color}╰{'─' * (MessageBox.BOX_WIDTH - 2)}╯{border_reset}"
        console.print(box_bottom)
        print("\n")  # Extra newline after box

def render_stream_event(event: Dict[str, Any], renderer: MessageRenderer) -> None:
    stream_type = event.get("stream_type")
    node_name = event.get("node_name")
    
    # Always log full events in debug mode 
    if CLI_CONFIG["debug"]:
        console.print(f"\n[dim cyan][DEBUG] Event: {event}[/dim cyan]")
    
    # Handle tool events first (highest priority)
    # Tools can come from both messages and values streams
    if "tool_name" in event:
        tool_name = event["tool_name"].upper()
        tool_input = ""
        tool_result = event.get("tool_result", "")
        agent = event.get("agent", "")
        
        # Format tool input nicely
        if isinstance(event.get("tool_input"), dict):
            if "allow" in event.get("tool_input", {}):
                tool_input = f"allow: {event.get('tool_input', {}).get('allow', '')}"
            else:
                tool_input = json.dumps(event.get("tool_input", {}), indent=2)
        else:
            tool_input = str(event.get("tool_input", ""))
        
        # Always show which agent called the tool
        if not agent:
            # If metadata is missing, try to infer from node name
            if node_name == "tools":
                agent = "superego"
            elif node_name == "inner_tools" or node_name == "inner_agent":
                agent = "inner_agent"
        
        # Finally render the tool information with all metadata
        renderer.render_tool_call(node_name, tool_name, tool_input, tool_result, agent)
        return  # Exit early once we've handled a tool
        
    # Handle regular message events
    if stream_type == "messages" and "content" in event:
        content = event["content"]
        if content and not content.isspace():
            # Skip tool messages as they're handled separately
            if node_name == "tools" and content == "true":
                return
                
            # Check if this is the end of a complete message
            is_end = event.get("end_of_message", False)
            if is_end and not content.endswith('\n'):
                content += '\n'
            
            renderer.render_agent_message(node_name, content)
    
    elif stream_type == "values":
        # Show routing info only in debug mode
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"] and node_name:
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
        renderer.reset()
        
        console.print("[bold blue]User:[/bold blue]", end=" ")
        user_input = input()
        if user_input.lower() in ["exit", "quit"]:
            console.print("[cyan]\Exiting Flow.[/cyan]")
h            break
            
        add_user_message(session_id, user_input)
        
        if CLI_CONFIG["debug"] and CLI_CONFIG["show_routing"]:
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

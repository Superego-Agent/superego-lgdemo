from colorama import Fore, Back, Style, init
import json
import argparse
import os
from typing import Dict, Any, Optional, List

# Import core logic from the new frontend-agnostic core module
from superego_core import (
    create_models, 
    create_workflow, 
    get_or_create_session,
    add_user_message,
    run_session
)

# Import constitution management functions from the dedicated module
from constitution_manager import (
    list_constitutions,
    view_constitution,
    edit_constitution,
    create_new_constitution,
    delete_constitution_cmd,
    switch_constitution,
    constitution_menu
)

# Initialize colorama for colored console output
init(autoreset=True)

# CLI settings
CLI_CONFIG = {
    "debug": False,         # Show debug info
    "show_routing": True,   # Show graph routing
    "editor": os.environ.get("EDITOR", "nano"),  # Default editor for editing constitutions
}

# CLI styling configurations
CLI_STYLES = {
    "DEBUG": Fore.CYAN + Style.DIM,
    "SYSTEM": Fore.YELLOW,
    "SUCCESS": Fore.GREEN + Style.BRIGHT,
    "NOTICE": Fore.MAGENTA,
    "ROUTING": Fore.BLUE + Style.BRIGHT,
    "ERROR": Fore.RED + Style.BRIGHT,
    "SUPEREGO": Fore.YELLOW,
    "CLAUDE": Fore.GREEN + Style.BRIGHT,
    "USER": Fore.BLUE + Style.BRIGHT,
    "TOOL": Fore.MAGENTA, 
}

def visualize_workflow():
    """Print a visual representation of the workflow."""
    print(Fore.CYAN + "\n" + "=" * 60)
    print(Fore.CYAN + "WORKFLOW VISUALIZATION:")
    print(Fore.CYAN + "START")
    print(Fore.CYAN + "  ↓")
    print(Fore.CYAN + "SUPEREGO (Moderation)")
    print(Fore.CYAN + "  ↓")
    print(Fore.CYAN + "TOOLS (ALLOW/BLOCK Decision)")
    print(Fore.CYAN + "  ↓")
    print(Fore.CYAN + "Should Continue? ─── Yes ──→ INNER AGENT → END")
    print(Fore.CYAN + "      │")
    print(Fore.CYAN + "      No")
    print(Fore.CYAN + "      ↓")
    print(Fore.CYAN + "     END")
    print(Fore.CYAN + "=" * 60 + "\n")

def render_stream_event(event: Dict[str, Any]) -> None:
    """Render a streaming event to the console."""
    stream_type = event.get("stream_type")
    node_name = event.get("node_name")
    
    # Handle message chunks (token streaming)
    if stream_type == "messages" and "content" in event:
        content = event["content"]
        
        # Display content based on node attribution
        if node_name == "superego" and content:
            # Handle transition from inner agent back to superego
            if hasattr(render_stream_event, "inner_started") and not hasattr(render_stream_event, "superego_started"):
                print("\n")
                
            # Only print the label once 
            if not hasattr(render_stream_event, "superego_started"):
                print(CLI_STYLES["SUPEREGO"] + "Superego: " + Style.RESET_ALL, end="")
                render_stream_event.superego_started = True
                # Clear inner agent flag if we're starting superego output again
                if hasattr(render_stream_event, "inner_started"):
                    delattr(render_stream_event, "inner_started")
            
            # Print content
            print(content, end="", flush=True)
                
        elif node_name == "inner_agent" and content:
            # Only insert a newline when transitioning from superego to inner agent
            if hasattr(render_stream_event, "superego_started") and not hasattr(render_stream_event, "inner_started"):
                print("\n")
                # Clear superego flag as we're now in inner agent output
                delattr(render_stream_event, "superego_started")
                
            # Print the label once when transitioning to inner agent
            if not hasattr(render_stream_event, "inner_started"):
                print(CLI_STYLES["CLAUDE"] + "Claude: " + Style.RESET_ALL, end="")
                render_stream_event.inner_started = True
                
            # Print content
            print(content, end="", flush=True)
    
    # Handle state updates - this is where tool calls come in
    elif stream_type == "values":
        # Show routing if enabled
        if CLI_CONFIG["show_routing"] and node_name:
            print(f"\n{CLI_STYLES['ROUTING']}[ROUTING] → {node_name.upper()}")
        
        # Always log values for debugging if debug is enabled
        if CLI_CONFIG["debug"]:
            print(f"\n{CLI_STYLES['DEBUG']}[DEBUG] Event: {event}")
        
        # SIMPLE CONSISTENT APPROACH: Display ANY tool call from ANY node
        # Just check if tool_name exists in the event or state (in any location)
        tool_name = None
        tool_input = ""
        tool_result = ""
        agent_name = "Superego" if node_name == "tools" else "Claude"
        
        # Try to find tool info directly in event
        if "tool_name" in event:
            tool_name = event["tool_name"]
            tool_input = event.get("tool_input", "")
            tool_result = event.get("tool_result", "")
            
        # Also check nested state for tool info
        elif "state" in event and isinstance(event["state"], dict) and "tool_name" in event["state"]:
            tool_name = event["state"]["tool_name"]
            tool_input = event["state"].get("tool_input", "")
            tool_result = event["state"].get("tool_result", "")
            
        # If we found a tool call, display it with a consistent format
        if tool_name:
            # Add a newline first if we're still displaying text
            if hasattr(render_stream_event, "superego_started") or hasattr(render_stream_event, "inner_started"):
                print("\n")
            
            # Show ALL tool calls with one simple format
            print(CLI_STYLES["TOOL"] + f"[TOOL] {agent_name} called: {tool_name}" + Style.RESET_ALL)
            if tool_input:
                print(CLI_STYLES["TOOL"] + f"Input: {tool_input}" + Style.RESET_ALL)
            if tool_result:
                print(CLI_STYLES["TOOL"] + f"Result: {tool_result}" + Style.RESET_ALL)

def chat_loop(session_id: Optional[str] = None, debug: bool = False):
    """Run the chat loop for CLI interface."""
    # Set debug mode locally
    CLI_CONFIG["debug"] = debug
    
    # Create workflow
    superego_model, inner_model = create_models()
    app = create_workflow(superego_model, inner_model)
    
    # Get or create session
    session_id = get_or_create_session(session_id)
    
    # Print header
    print(Fore.CYAN + Style.BRIGHT + "╔════════════════════════════════════════════════════════════╗")
    print(Fore.CYAN + Style.BRIGHT + "║                    SUPEREGO CHAT SYSTEM                    ║") 
    print(Fore.CYAN + Style.BRIGHT + "╚════════════════════════════════════════════════════════════╝")
    print(Fore.WHITE + f"Starting chat with moderation (Session: {session_id})")
    if CLI_CONFIG["debug"]:
        print(Fore.CYAN + "[DEBUG MODE ACTIVE]")
    print(Fore.WHITE + "Type 'exit' or 'quit' to end.\n")
    
    # Display workflow visualization
    if CLI_CONFIG["show_routing"]:
        visualize_workflow()
    
    while True:
        # Clear state variables
        for attr in ["superego_started", "inner_started", "last_node", "pending_newline"]:
            if hasattr(render_stream_event, attr):
                delattr(render_stream_event, attr)
            
        # Get user input
        user_input = input(CLI_STYLES["USER"] + "User: " + Style.RESET_ALL)
        if user_input.lower() in ["exit", "quit"]:
            print(Fore.CYAN + "\nThank you for using Superego Chat. Goodbye!")
            break
            
        # Add user message to session
        add_user_message(session_id, user_input)
        
        # Display workflow start
        if CLI_CONFIG["show_routing"]:
            print(f"{CLI_STYLES['ROUTING']}[ROUTING] STARTING WORKFLOW")
            print(f"{CLI_STYLES['ROUTING']}[ROUTING] → START")
        
        # Run session and get streaming events
        for event in run_session(session_id, app):
            render_stream_event(event)
        
        # Show end of workflow
        if CLI_CONFIG["show_routing"]:
            print(f"\n{CLI_STYLES['ROUTING']}[ROUTING] → END OF WORKFLOW")
        
        # Add a newline for better readability
        print()


def main_menu():
    """Show the main menu for the application."""
    while True:
        print(Fore.CYAN + Style.BRIGHT + "\n╔════════════════════════════════════════════════════════════╗")
        print(Fore.CYAN + Style.BRIGHT + "║                    SUPEREGO CHAT SYSTEM                    ║") 
        print(Fore.CYAN + Style.BRIGHT + "╚════════════════════════════════════════════════════════════╝")
        
        print(Fore.CYAN + "\nMAIN MENU:")
        print(Fore.WHITE + "1. Start Chat")
        print(Fore.WHITE + "2. Manage Constitutions")
        print(Fore.WHITE + "3. Exit")
        
        choice = input(Fore.YELLOW + "\nEnter your choice (1-3): ")
        
        if choice == "1":
            # Start chat with a new session
            chat_loop(debug=CLI_CONFIG["debug"])
        elif choice == "2":
            # Manage constitutions, passing the editor config
            constitution_menu(editor=CLI_CONFIG["editor"])
        elif choice == "3":
            # Exit
            print(Fore.CYAN + "\nThank you for using Superego Chat. Goodbye!")
            break
        else:
            print(Fore.RED + "Invalid choice. Please enter a number from 1-3.")

def main():
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="Superego Chat CLI")
    parser.add_argument("--session", "-s", help="Session ID to resume (creates a new one if not provided)")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug output")
    parser.add_argument("--list-constitutions", "-l", action="store_true", help="List available constitutions")
    parser.add_argument("--view-constitution", "-v", metavar="ID", help="View a specific constitution")
    parser.add_argument("--edit-constitution", "-e", metavar="ID", help="Edit a specific constitution")
    parser.add_argument("--create-constitution", "-c", metavar="ID", help="Create a new constitution")
    parser.add_argument("--delete-constitution", metavar="ID", help="Delete a constitution")
    parser.add_argument("--switch-constitution", metavar="ID", help="Switch to a different constitution")
    parser.add_argument("--menu", "-m", action="store_true", help="Show interactive menu")
    
    args = parser.parse_args()
    
    # Set debug mode if passed
    if args.debug:
        CLI_CONFIG["debug"] = True
    
    # Handle constitution management commands
    if args.list_constitutions:
        list_constitutions()
        return
    
    if args.view_constitution:
        view_constitution(args.view_constitution)
        return
    
    if args.edit_constitution:
        edit_constitution(args.edit_constitution, editor=CLI_CONFIG["editor"])
        return
    
    if args.create_constitution:
        create_new_constitution(args.create_constitution, editor=CLI_CONFIG["editor"])
        return
    
    if args.delete_constitution:
        delete_constitution_cmd(args.delete_constitution)
        return
    
    if args.switch_constitution:
        switch_constitution(args.switch_constitution)
        return
    
    # Show menu or start chat
    if args.menu:
        main_menu()
    else:
        # By default, show menu if no session specified
        if args.session:
            chat_loop(session_id=args.session, debug=CLI_CONFIG["debug"])
        else:
            if args.debug:
                # If debug flag is set but no session provided, start chat with debug mode
                chat_loop(debug=True)
            else:
                main_menu()

if __name__ == "__main__":
    main()

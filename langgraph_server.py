"""
LangGraph Server for the Superego system.

This file is a simple convenience wrapper to run the LangGraph server.
You can also use the LangGraph CLI directly:
    langgraph dev
"""

import subprocess
import sys
import os
import webbrowser
from pathlib import Path

def run_langgraph_server():
    """Run the LangGraph server with the Superego graph."""
    print("Starting LangGraph Server with Superego graph...")
    print("This will connect to LangGraph Studio for visualization.")
    
    # Check if langgraph-cli is installed
    try:
        subprocess.run(["langgraph", "--version"], 
                      capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("langgraph-cli not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-U", "langgraph-cli[inmem]>=0.1.55"], 
                      check=True)

    # Run the server
    try:
        # Find the langgraph.json file
        langgraph_config = Path(__file__).parent / "langgraph.json"
        if not langgraph_config.exists():
            print(f"Error: {langgraph_config} not found. Make sure it exists.")
            sys.exit(1)
            
        # Start the server - this will automatically open the browser to LangGraph Studio
        subprocess.run(["langgraph", "dev"], cwd=Path(__file__).parent)
    except KeyboardInterrupt:
        print("\nLangGraph Server stopped.")
        
if __name__ == "__main__":
    run_langgraph_server()

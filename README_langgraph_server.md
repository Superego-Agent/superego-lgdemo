# SuperEgo with LangGraph Server

This project has been enhanced to use LangGraph Server, allowing you to leverage LangGraph Studio for visualization and debugging.

## Overview

The implementation adds LangGraph Server support while preserving all existing functionality. The key changes are:

1. Added a `langgraph.json` configuration file that exposes the graph to LangGraph Server
2. Modified `superego_core.py` to initialize and export the graph
3. Added a convenience wrapper script `langgraph_server.py`

## Benefits

- **Interactive Visualization**: Use LangGraph Studio to visualize the flow of your agent
- **Standard API Endpoints**: Access all standard LangGraph API endpoints for threads, runs, assistants, etc.
- **Future Compatibility**: This structure makes it easier to convert SuperEgo into a prebuilt LangGraph component or subgraph
- **Debugging Tools**: Gain access to debugging tools, time travel, and persistence features

## How to Use

### Option 1: Use the convenience wrapper

```bash
python langgraph_server.py
```

This script will:
- Check if langgraph-cli is installed and install it if needed
- Start the server and open LangGraph Studio in your browser

### Option 2: Use the LangGraph CLI directly

If you already have the LangGraph CLI installed, you can run:

```bash
# Make sure you have the CLI installed
pip install -U "langgraph-cli[inmem]>=0.1.55"

# Start the server
langgraph dev
```

## Future Extensibility

This implementation sets you up for future plans to make SuperEgo into a prebuilt LangGraph agent or component:

1. **Subgraph Capability**: You can now easily use SuperEgo as a layer in front of another graph or subgraph
2. **Library Pattern**: The current structure follows the standard pattern for shareable LangGraph components
3. **Simplified Integration**: Makes it easier to integrate with other LangGraph-based applications

## Notes

- The original CLI interface (`python main.py` or `python cli.py`) still works as before
- The LangGraph server provides an additional way to interact with the system
- The server automatically connects to LangGraph Studio for visualization

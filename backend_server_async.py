# src/backend_server_async.py

# Standard library imports
import os
import traceback
from contextlib import asynccontextmanager
from typing import Any, Optional  # Keep Any for graph_app type hint

# Third-party imports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,  # Keep for checkpointer type hint
)

# Langchain/Langgraph specific imports
# from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk # Likely removable
from langgraph.checkpoint.sqlite.aio import (
    AsyncSqliteSaver,  # Keep for lifespan type check
)

# from sse_starlette.sse import EventSourceResponse, ServerSentEvent # Likely removable


# Project-specific imports
try:
    from config import CONFIG  # Keep temporarily

    # Import only get_constitution_content if get_available_constitutions is only used in the router
    from constitution_utils import (  # Keep temporarily
        get_constitution_content,
        get_constitution_hierarchy,
    )
    from superego_core_async import create_models, create_workflow  # Keep for lifespan
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print(
        "Ensure backend_server_async.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH."
    )
    import sys

    sys.exit(1)

# Import Routers
from api_routers import constitutions as constitutions_router
from api_routers import runs as runs_router
from api_routers import threads as threads_router

# --- Globals ---
graph_app: Any = None
checkpointer: Optional[BaseCheckpointSaver] = None  # Use BaseCheckpointSaver hint
inner_agent_app: Any = None


# --- Lifespan Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown logic."""
    global graph_app, checkpointer, inner_agent_app
    print("Backend server starting up...")
    try:
        superego_model, inner_model = create_models()
        graph_app, checkpointer, inner_agent_app = await create_workflow(
            superego_model=superego_model, inner_model=inner_model
        )
        if not checkpointer:
            print("Warning: Checkpointer was not initialized during startup.")
        if not graph_app:
            print("Warning: Main graph app was not initialized.")
        if not inner_agent_app:
            print("Warning: Inner agent app was not initialized.")

        print("Models, graph, and databases initialized successfully.")

        # Pass instances to routers after they are created
        # This ensures routers have access to the necessary components
        if graph_app:
            runs_router.router.graph_app_instance = graph_app
            print("Passed graph_app instance to runs_router.")
        if checkpointer:
            runs_router.router.checkpointer_instance = checkpointer
            threads_router.router.checkpointer_instance = checkpointer
            print("Passed checkpointer instance to runs_router and threads_router.")
        # Pass graph_app instance to threads_router as well
        if graph_app:
            threads_router.router.graph_app_instance = graph_app
            print("Passed graph_app instance to threads_router.")

    except Exception as e:
        print(f"FATAL: Error during startup: {e}")
        traceback.print_exc()
        raise RuntimeError("Failed to initialize backend components") from e

    yield

    # --- Shutdown ---
    print("Backend server shutting down...")
    if (
        checkpointer
        and isinstance(checkpointer, AsyncSqliteSaver)
        and checkpointer.conn
    ):
        try:
            print("Attempting to close checkpointer DB connection...")
            await checkpointer.conn.close()
            print("Checkpointer DB connection closed.")
        except Exception as e:
            print(f"Warning: Error closing checkpointer connection: {e}")


# --- FastAPI App ---
# Pass the lifespan manager to the FastAPI app instance
app = FastAPI(title="Superego Backend", lifespan=lifespan)


@app.get("/")
def healthcheck():
    return {"status": "ok"}


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Include API Routers ---
# Include the routers after the FastAPI app is defined
app.include_router(runs_router.router)
app.include_router(threads_router.router)
app.include_router(constitutions_router.router)
print("Included API routers.")


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn

    if not os.getenv("ANTHROPIC_API_KEY"):
        print(
            "WARNING: ANTHROPIC_API_KEY environment variable not set. LangGraph models may fail."
        )

    # Explicitly bind to 127.0.0.1 for testing localhost connection
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    reload = os.getenv("BACKEND_RELOAD", "true").lower() == "true"

    print(
        f"Starting Uvicorn server on {host}:{port} (Reload: {'enabled' if reload else 'disabled'})"
    )
    uvicorn.run(
        "backend_server_async:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )

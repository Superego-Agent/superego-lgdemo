# src/backend_server_async.py

# Standard library imports
import os
import uuid
import json
import asyncio
import traceback
import logging # Import logging module
import requests # Added for Mailgun API call
from contextlib import asynccontextmanager
from typing import List, Dict, Optional, Any, Literal, Union, AsyncGenerator, Tuple
from datetime import datetime, timedelta, timezone # Added timedelta, timezone for JWT

# Third-party imports
import aiosqlite # Keep for potential direct interaction if needed, though manager preferred
from fastapi import FastAPI, HTTPException, Body, Path as FastApiPath, Request, Response, status, Depends # Added Response, status, Depends
from fastapi.responses import RedirectResponse # Added for redirects
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field, EmailStr # Added EmailStr for potential future use
from starlette.middleware.sessions import SessionMiddleware # For storing state during OAuth flow
from starlette.requests import Request as StarletteRequest # For type hinting in callback

# Authentication / OAuth imports
from dotenv import load_dotenv # To load .env file
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from jose import jwt, JWTError # Import directly from jose, also import JWTError
# from jwt import PyJWTError # PyJWTError is specific to PyJWT, use JWTError from jose

# Langchain/Langgraph specific imports
from langchain_core.messages import HumanMessage, BaseMessage, ToolMessage, AIMessage, AIMessageChunk
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.base import CheckpointTuple, BaseCheckpointSaver # Import BaseCheckpointSaver for type hint

# Project-specific imports
try:
    from config import CONFIG # Assumed to exist and be configured
    # Import get_constitution_content as well
    from constitution_utils import get_available_constitutions, get_combined_constitution_content, get_constitution_content
    from superego_core_async import create_models, create_workflow # Assumed to exist
    # Removed metadata_manager import
except ImportError as e:
    print(f"Error importing project modules: {e}")
    print("Ensure backend_server_async.py is run from the correct directory or superego-lgdemo modules are in PYTHONPATH.")
    import sys
    sys.exit(1)

# --- Load Environment Variables ---
load_dotenv() # Load variables from .env file

# --- Authentication / OAuth Configuration ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.getenv("SECRET_KEY") # For signing JWTs
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

# Ensure critical OAuth variables are set
if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY]):
    print("FATAL: Missing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, or SECRET_KEY in environment variables.")
    # sys.exit(1) # Consider exiting in production, but allow running locally for testing other parts

# Google OAuth Scopes - Requesting email and profile info
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid' # Standard OIDC scope
]
# The URL the user will be redirected to *from Google* after authentication
# Must match one of the Authorized redirect URIs in Google Cloud Console
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback")
# The URL of your frontend app, where the user is sent *after* successful login in the callback
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173") # Default to Vite dev server

# --- Globals ---
graph_app: Any = None
checkpointer: Optional[BaseCheckpointSaver] = None # Use BaseCheckpointSaver hint
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
            superego_model=superego_model,
            inner_model=inner_model
        )
        if not checkpointer:
             print("Warning: Checkpointer was not initialized during startup.")
        if not graph_app:
             print("Warning: Main graph app was not initialized.")
        if not inner_agent_app:
             print("Warning: Inner agent app was not initialized.")


        print("Models, graph, and databases initialized successfully.")
    except Exception as e:
        print(f"FATAL: Error during startup: {e}")
        traceback.print_exc()
        raise RuntimeError("Failed to initialize backend components") from e

    yield 

    # --- Shutdown ---
    print("Backend server shutting down...")
    if checkpointer and isinstance(checkpointer, AsyncSqliteSaver) and checkpointer.conn:
         try:
              print("Attempting to close checkpointer DB connection...")
              await checkpointer.conn.close()
              print("Checkpointer DB connection closed.")
         except Exception as e:
              print(f"Warning: Error closing checkpointer connection: {e}")

# --- FastAPI App ---
app = FastAPI(title="Superego Backend", lifespan=lifespan)

# --- Session Middleware (Required for OAuth state) ---
# Add a *different* secret key for session middleware state. It can be the same as SECRET_KEY
# but using a separate one is slightly better practice if you have complex middleware needs.
# For simplicity here, we'll reuse SECRET_KEY if it exists, otherwise warn.
SESSION_MIDDLEWARE_KEY = SECRET_KEY or "fallback_session_key_please_set_secret_key"
if not SECRET_KEY:
    print("Warning: SECRET_KEY not set, using insecure fallback for session middleware.")
app.add_middleware(SessionMiddleware, secret_key=SESSION_MIDDLEWARE_KEY)


# --- CORS ---
# Ensure your frontend origin is allowed, especially if running on a different port
# For development, allowing localhost:5173 is crucial.
# Using ["*"] is convenient for local dev but be more specific in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_credentials=True, # Original - Keep this one
    allow_methods=["*"],
    allow_headers=["*"],
    # Allow cookies to be sent with requests (needed for JWT session)
    allow_credentials=True, # Duplicate - Remove this one
)


# --- JWT Helper Functions ---

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration time
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Pydantic Models ---
# Add models for user info if needed
class UserInfo(BaseModel):
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    # Add other fields you might get from Google profile

# Ensure these match frontend expectations (src/global.d.ts)

# Models for referencing constitutions in requests
# These now match the structure sent from the frontend (BackendConstitutionRefById/FullText in global.d.ts)
class ConstitutionRefById(BaseModel):
    id: str = Field(..., description="ID of a globally available constitution.")
    title: str = Field(..., description="Title of the constitution (used for reporting).")
    adherence_level: int = Field(..., ge=1, le=5, description="User-specified adherence level (1-5).")

class ConstitutionFullText(BaseModel):
    title: str = Field(..., description="Title of the local constitution (used for reporting).")
    text: str = Field(..., description="Raw text content of a locally defined constitution.")
    adherence_level: int = Field(..., ge=1, le=5, description="User-specified adherence level (1-5).")

# Model for listing available constitutions
class ConstitutionItem(BaseModel):
    id: str
    title: str # Changed from 'name' to 'title' to match constitution_utils
    description: Optional[str] = None

class HistoryMessage(BaseModel):
    id: str # Unique ID for the message within its history context
    sender: Literal['human', 'ai', 'tool_result', 'system']
    content: Any # Allow flexibility, will be serialized
    timestamp: Optional[int] = None
    node: Optional[str] = None
    set_id: Optional[str] = None # Keep for compare mode differentiation in frontend
    tool_name: Optional[str] = None # Specific to tool_result sender
    is_error: Optional[bool] = None # Specific to tool_result or system sender
    tool_calls: Optional[List[Dict[str, Any]]] = None # Specific to ai sender

class HistoryResponse(BaseModel):
    messages: List[HistoryMessage]
    thread_id: str

class StreamRunInput(BaseModel):
    type: Literal["human"]
    content: str

class StreamRunRequest(BaseModel):
    # Now uses the string checkpoint thread ID (UUID)
    thread_id: Optional[str] = None
    input: StreamRunInput
    # Updated field to accept the new constitution models including title and adherence level
    constitutions: List[Union[ConstitutionRefById, ConstitutionFullText]] = Field(..., description="List of selected constitutions (global by ID, local by text) with titles and adherence levels.")
    # Removed: adherence_levels_text: Optional[str] = None # This field is no longer sent by the frontend

class CompareRunSet(BaseModel):
    id: str
    # Updated to use the new constitution models, consistent with StreamRunRequest
    constitutions: List[Union[ConstitutionRefById, ConstitutionFullText]] = Field(..., description="List of constitutions (global by ID, local by text) with titles and adherence levels for this comparison set.")

class CompareRunRequest(BaseModel):
    # Now uses the string checkpoint thread ID (UUID)
    thread_id: Optional[str] = None
    input: StreamRunInput
    constitution_sets: List[CompareRunSet]

# SSE Event Data Models (matching global.d.ts SSEEventData)

class SSEThreadCreatedData(BaseModel):
    thread_id: str 

class SSEToolCallChunkData(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    args: Optional[str] = None

class SSEToolResultData(BaseModel):
    tool_name: str
    result: str
    is_error: bool
    tool_call_id: Optional[str] = None

class SSEEndData(BaseModel):
    thread_id: str

class SSEEventData(BaseModel):
    type: Literal["thread_created", "chunk", "ai_tool_chunk", "tool_result", "error", "end"]
    node: Optional[str] = None
    data: Union[SSEThreadCreatedData, str, SSEToolCallChunkData, SSEToolResultData, SSEEndData]
    set_id: Optional[str] = None # For compare mode tracking

# Model for submitting a constitution for review
class SubmitConstitutionRequest(BaseModel):
    title: str = Field(..., description="Title of the constitution being submitted.")
    text: str = Field(..., description="Full text content of the constitution being submitted.")
    isPrivate: bool = Field(..., description="Whether the submitted constitution should be kept private.")
    # submitter_email: Optional[EmailStr] = Field(None, description="Optional email of the submitter.") # Example for future extension

# --- Helper Function for Standard Streaming ---
async def stream_events(
    thread_id: str, # The unique LangGraph thread ID (string UUID) for this specific run
    input_messages: List[BaseMessage],
    constitutions: List[Union[ConstitutionRefById, ConstitutionFullText]], # Updated type hint
    run_app: Any, # The compiled LangGraph app to run
    # Removed: adherence_levels_text: Optional[str] = None,
    set_id: Optional[str] = None # Identifier for compare mode sets
) -> AsyncGenerator[ServerSentEvent, None]:
    """Generates Server-Sent Events for a single LangGraph run, processing constitutions, generating adherence report."""
    if not run_app or not checkpointer:
        error_data = "Graph app or checkpointer not initialized."
        yield ServerSentEvent(data=SSEEventData(type="error", node="setup", data=error_data, set_id=set_id).model_dump_json())
        return

    current_node_name: Optional[str] = None
    last_yielded_text: Dict[Tuple[Optional[str], Optional[str]], str] = {}
    # run_id_for_db removed

    try:
        # --- Load constitution content and generate adherence report ---
        constitution_texts: List[str] = []
        adherence_report_lines: List[str] = []
        missing_ids: List[str] = []

        # Check if any non-'none' constitutions were provided
        valid_constitutions = [
            c for c in constitutions
            if not (isinstance(c, ConstitutionRefById) and c.id == "none")
        ]

        # Add header only if there are valid constitutions to report on
        if valid_constitutions:
             adherence_report_lines.append("# User-specified Adherence Levels")

        for ref in constitutions:
            # Skip the special 'none' constitution placeholder if present
            if isinstance(ref, ConstitutionRefById) and ref.id == "none":
                continue

            content = None
            title = ref.title
            level = ref.adherence_level

            if isinstance(ref, ConstitutionRefById):
                # ID-based constitution (global)
                content = get_constitution_content(ref.id)
                if content is not None:
                    constitution_texts.append(content)
                else:
                    missing_ids.append(ref.id)
                    # Skip reporting missing ones to avoid confusion in the report
                    continue # Skip to next constitution if content not found

            elif isinstance(ref, ConstitutionFullText):
                # Text-based constitution (local)
                content = ref.text
                constitution_texts.append(content)
            # else: # Should not happen with Pydantic validation

            # Add to adherence report (only if content was successfully loaded/provided)
            default_tag = " (Default)" if level == 3 else ""
            adherence_report_lines.append(f"- {title}: {level}/5{default_tag}")


        # Combine constitution texts
        base_constitution_content = "\n\n---\n\n".join(constitution_texts)

        # Combine adherence report lines
        adherence_report_text = "\n".join(adherence_report_lines)

        # Combine base content and adherence report
        # Append report only if it has more than just the header (or if header wasn't added)
        final_constitution_content = base_constitution_content
        if len(adherence_report_lines) > (1 if valid_constitutions else 0):
            final_constitution_content += f"\n\n---\n\n{adherence_report_text}"

        # Report missing IDs (if any)
        if missing_ids:
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="setup", # Using 'error' type for warnings as well
                data=f"Warning: Constitution ID(s) not found/loaded: {', '.join(missing_ids)}. Running without them.",
                set_id=set_id
            ).model_dump_json())
        # --- End Constitution Processing ---

        # Prepare run config using the UNIQUE thread_id for this run
        config = {
            "configurable": {
                "thread_id": thread_id, # Use the passed thread_id here
                "constitution_content": final_constitution_content # Pass the combined content + report
            }
        }
        stream_input = {'messages': input_messages}

        # Stream events from the LangGraph app
        stream = run_app.astream_events(stream_input, config=config, version="v1")

        async for event in stream:
            event_type = event.get("event")
            event_name = event.get("name")
            tags = event.get("tags", [])
            event_data = event.get("data", {})

            # --- Track Current Node ---
            potential_node_tags = [tag for tag in tags if tag in ["superego", "inner_agent", "tools"]]
            if event_name in ["superego", "inner_agent", "tools"]:
                 current_node_name = event_name
            elif potential_node_tags:
                 current_node_name = potential_node_tags[-1] # Use the last relevant tag found

            yield_key = (current_node_name, set_id) # Key for deduplicating text chunks

            # --- Process Different Event Types ---
            # (Chunk, Tool Chunk, Tool Result processing logic remains largely the same as before)
            # Text Chunk Events
            if event_type == "on_chat_model_stream" and isinstance(event_data.get("chunk"), AIMessageChunk):
                chunk: AIMessageChunk = event_data["chunk"]
                text_content = ""
                if isinstance(chunk.content, str):
                    text_content = chunk.content
                elif isinstance(chunk.content, list):
                    for item in chunk.content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_content += item.get("text", "")
                            elif item.get("type") == "content_block_delta" and item.get("delta", {}).get("type") == "text_delta":
                                 text_content += item.get("delta", {}).get("text", "")

                if text_content:
                    last_text = last_yielded_text.get(yield_key, "")
                    if text_content != last_text:
                        sse_payload_text = SSEEventData(type="chunk", node=current_node_name, data=text_content, set_id=set_id)
                        yield ServerSentEvent(data=sse_payload_text.model_dump_json())
                        last_yielded_text[yield_key] = text_content

            # Tool Call Chunk Events - Ensure this is 'if', not 'elif'
            if event_type == "on_chat_model_stream" and isinstance(event_data.get("chunk"), AIMessageChunk):
                 # Re-access chunk data as the previous 'if' might have consumed it conceptually
                 chunk_for_tools: AIMessageChunk = event_data["chunk"]
                 tool_chunks = getattr(chunk_for_tools, 'tool_call_chunks', [])
                 if tool_chunks:
                     for tc_chunk in tool_chunks:
                         # Ensure args is always sent as a string or None
                         args_value = tc_chunk.get("args")
                         args_str: Optional[str] = None
                         if args_value is not None:
                             if isinstance(args_value, str):
                                 args_str = args_value
                             else:
                                 try:
                                     # Attempt to JSON dump non-string args fragments
                                     args_str = json.dumps(args_value)
                                 except Exception:
                                     # Fallback to simple string conversion if JSON fails
                                     args_str = str(args_value)

                         chunk_data = SSEToolCallChunkData(
                             id=tc_chunk.get("id"),
                             name=tc_chunk.get("name"),
                             args=args_str # Use the explicitly stringified version
                         )
                         sse_payload_tool = SSEEventData(type="ai_tool_chunk", node=current_node_name, data=chunk_data, set_id=set_id)
                         yield ServerSentEvent(data=sse_payload_tool.model_dump_json())


            # Tool Result Events
            elif event_type == "on_tool_end":
                 tool_output = event_data.get("output")
                 try:
                      output_str = json.dumps(tool_output) if not isinstance(tool_output, str) else tool_output
                 except Exception:
                      output_str = str(tool_output)

                 tool_func_name = event.get("name")
                 is_error = isinstance(tool_output, Exception)
                 tool_call_id = None
                 parent_ids = event_data.get("parent_run_ids")
                 if isinstance(parent_ids, list):
                      possible_ids = [pid for pid in parent_ids if isinstance(pid, str)]
                      if possible_ids:
                         tool_call_id = possible_ids[-1]

                 sse_payload_data = SSEToolResultData(
                     tool_name=tool_func_name or "unknown_tool",
                     result=output_str,
                     is_error=is_error,
                     tool_call_id=tool_call_id
                 )
                 sse_payload = SSEEventData(type="tool_result", node="tools", data=sse_payload_data, set_id=set_id)
                 yield ServerSentEvent(data=sse_payload.model_dump_json())

        # --- Stream End ---
        # Pass the thread_id (string UUID) back to the frontend
        yield ServerSentEvent(data=SSEEventData(type="end", node=current_node_name or "graph", data=SSEEndData(thread_id=thread_id), set_id=set_id).model_dump_json())

        # Removed post-stream checkpoint update logic related to metadata DB

    except Exception as e:
        print(f"Stream Error (Thread ID: {thread_id}, Set: {set_id}): {e}")
        traceback.print_exc()
        try:
            error_data = f"Streaming error: {str(e)}"
            # Ensure thread_id is sent even in error/end events
            yield ServerSentEvent(data=SSEEventData(type="error", node=current_node_name or "graph", data=error_data, set_id=set_id).model_dump_json())
            yield ServerSentEvent(data=SSEEventData(type="end", node="error", data=SSEEndData(thread_id=thread_id), set_id=set_id).model_dump_json()) # Send end on error too
        except Exception as inner_e:
            print(f"Failed to send stream error event: {inner_e}")


# --- API Endpoints ---

@app.get("/api/constitutions", response_model=List[ConstitutionItem])
async def get_constitutions_endpoint():
    """Returns a list of available constitutions with title and description."""
    try:
        # get_available_constitutions now returns the desired structure with 'title'
        constitutions_dict = get_available_constitutions()

        response_items = []
        for const_id, metadata in constitutions_dict.items():
            if isinstance(metadata, dict):
                # Use 'title' from the metadata provided by the updated utility function
                response_items.append(ConstitutionItem(
                    id=const_id,
                    title=metadata.get('title', const_id.replace('_', ' ').title()), # Fallback if title missing
                    description=metadata.get('description')
                ))
            else:
                # This case should be less likely now with error handling in get_available_constitutions
                logging.warning(f"Constitution '{const_id}' has unexpected data format: {metadata}. Skipping.")
        return response_items
    except Exception as e:
        logging.error(f"Error loading constitutions in endpoint: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load constitutions: {str(e)}")


@app.get("/api/constitutions/{constitution_id}/content", response_model=str)
async def get_constitution_content_endpoint(
    constitution_id: str = FastApiPath(..., title="The ID of the constitution")
):
    """Returns the raw text content of a single constitution."""
    try:
        # Use the existing utility function to get content (handles 'none' and invalid IDs)
        content = get_constitution_content(constitution_id)
        if content is None:
            # Utility function returns None if ID is invalid or file not found
            raise HTTPException(status_code=404, detail=f"Constitution '{constitution_id}' not found or invalid.")
        # Return content directly as a string (FastAPI handles text/plain response)
        # Forcing text/plain might be better if FastAPI defaults to JSON for string response_model
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=content)
    except HTTPException:
        raise # Re-raise explicit HTTP exceptions
    except Exception as e:
        logging.error(f"Error getting content for constitution {constitution_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to load content for constitution '{constitution_id}'.")

@app.post("/api/constitutions/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_constitution_for_review(
    submission: SubmitConstitutionRequest = Body(...)
):
    """
    Accepts a constitution submission for potential global review.
    Currently logs the submission details.
    """
    # TODO: Implement actual storage/review mechanism (e.g., save to DB, notify admins)
    logging.info(f"Received constitution submission for review:")
    logging.info(f"  Title: {submission.title}")
    logging.info(f"  Text Length: {len(submission.text)} characters")
    logging.info(f"  Is Private: {submission.isPrivate}")
    # Optionally log the text itself, be mindful of log size/sensitivity
    # logging.debug(f"  Text: {submission.text[:200]}...") # Log snippet

    # --- Send Email Notification via Mailgun ---
    mailgun_api_key = os.getenv("MAILGUN_API_KEY")
    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    recipient_email = os.getenv("MAILGUN_RECIPIENT_EMAIL")

    email_sent_successfully = False
    email_error_message = ""
    
    if mailgun_api_key and mailgun_domain:
        subject = f"New Constitution Submitted: {submission.title}"
        body = (
            f"A new constitution has been submitted for review:\n\n"
            f"Title: {submission.title}\n"
            f"Private Submission: {'Yes' if submission.isPrivate else 'No'}\n\n"
            f"Text:\n---\n{submission.text}\n---"
        )
        sender_email = f"noreply@{mailgun_domain}" # Standard practice for sender

        try:
            response = requests.post(
                f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
                auth=("api", mailgun_api_key),
                data={"from": f"Superego Submission <{sender_email}>",
                      "to": [recipient_email],
                      "subject": subject,
                      "text": body})
            logging.info(f"Mailgun API Response: {response.status_code} - {response.text}")
            if response.status_code == 200:
                logging.info(f"Successfully sent submission email to {recipient_email}")
                email_sent_successfully = True
            else:
                logging.error(f"Mailgun API Error ({response.status_code}): {response.text}")
                email_error_message = f"Mailgun API Error ({response.status_code}). Check backend logs."
                email_sent_successfully = False

        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending email via Mailgun: {e}")
            email_error_message = f"Network error sending email: {e}"
            email_sent_successfully = False
        except Exception as e:
            logging.error(f"Unexpected error during email sending: {e}")
            traceback.print_exc()
            email_error_message = f"Unexpected error sending email: {e}"
            email_sent_successfully = False
    elif not mailgun_api_key:
        logging.warning("MAILGUN_API_KEY not configured. Skipping email notification.")
        email_error_message = "Mailgun API Key not configured."
    else: # Implies domain or recipient might be missing if API key is present
         logging.warning("Mailgun Domain or Recipient Email not configured correctly. Skipping email notification.")
         email_error_message = "Mailgun Domain/Recipient not configured."


    # You could add logic here to:
    # 1. Validate the constitution format/content further.
    # 2. Save the submission to a database table (e.g., 'submitted_constitutions').
    # 3. Send a notification (email, Slack, etc.) to reviewers.
    # 4. Return a unique ID for the submission if needed.

    final_message = "Constitution submitted for review."
    if email_sent_successfully:
        final_message += " Notification email sent."
    elif email_error_message:
         final_message += f" Failed to send notification email: {email_error_message}"

    # Return 202 Accepted regardless of email success, as the submission itself was received.
    # The client doesn't necessarily need to know about backend notification failures immediately.
    return {"message": final_message}


# Removed /api/threads and /api/threads/{thread_id}/rename endpoints

@app.get("/api/threads/{thread_id}/history", response_model=HistoryResponse)
async def get_thread_history_endpoint(
    thread_id: str = FastApiPath(..., title="The checkpoint thread ID (UUID string)")
):
    """Retrieves the message history for a specific checkpoint thread ID."""
    if not checkpointer:
        print("Error: Checkpointer not available for getting history.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    try:
        # Directly use the provided string thread_id with the checkpointer
        print(f"Fetching history using Checkpoint Thread ID: {thread_id}")
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple: Optional[CheckpointTuple] = await checkpointer.aget_tuple(config)

        # Process messages from the checkpoint tuple
        history_messages: List[HistoryMessage] = []
        if not checkpoint_tuple:
             print(f"No checkpoint found for thread_id: {thread_id}")
             # Return empty history but indicate the requested thread_id
             return HistoryResponse(messages=[], thread_id=thread_id)

        if checkpoint_tuple and checkpoint_tuple.checkpoint:
             messages_from_state = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
             # ... (message processing logic - human, ai, tool - copied from previous version) ...
             # --- Timestamp Handling ---
             ts_value = checkpoint_tuple.checkpoint.get("ts")
             base_timestamp_ms = None
             if ts_value and hasattr(ts_value, 'timestamp') and callable(ts_value.timestamp):
                  try:
                     base_timestamp_ms = int(ts_value.timestamp() * 1000)
                  except (TypeError, ValueError) as ts_err:
                      print(f"Warning: Could not convert timestamp '{ts_value}' ({type(ts_value)}) to UNIX ms for thread {thread_id}: {ts_err}")

             # --- Message Loop ---
             for i, msg in enumerate(messages_from_state):
                 sender: Optional[Literal['human', 'ai', 'tool_result', 'system']] = None
                 node: Optional[str] = None
                 formatted_content: Optional[str] = None
                 tool_name: Optional[str] = None
                 is_error: Optional[bool] = None

                 if isinstance(msg, HumanMessage):
                     sender = "human"
                     node = getattr(msg, 'name', None)
                     formatted_content = str(msg.content) if msg.content is not None else ""
                 elif isinstance(msg, AIMessage):
                     sender = "ai"
                     node = getattr(msg, 'name', 'ai')
                     raw_content = msg.content
                     content_str = ""
                     if isinstance(raw_content, list):
                         for item in raw_content:
                             if isinstance(item, dict) and item.get("type") == "text":
                                 content_str += item.get("text", "")
                     elif isinstance(raw_content, str): content_str = raw_content
                     elif raw_content is not None: content_str = str(raw_content)

                     tool_calls_str = ""
                     if tool_calls := getattr(msg, "tool_calls", None):
                         tool_calls_str = "\n".join([
                             f"-> Called Tool: {tc.get('name', 'N/A')}({json.dumps(tc.get('args', {}))})"
                             for tc in tool_calls if isinstance(tc, dict)
                         ])

                     if content_str and tool_calls_str: formatted_content = f"{content_str}\n{tool_calls_str}"
                     elif content_str: formatted_content = content_str
                     elif tool_calls_str: formatted_content = tool_calls_str # Keep this line for now, might remove if content should always be empty for pure tool calls
                     else: formatted_content = ""

                     # Prepare tool_calls structure for the response model
                     response_tool_calls = None
                     if tool_calls := getattr(msg, "tool_calls", None):
                         # Ensure it's a list of dicts before assigning
                         if isinstance(tool_calls, list) and all(isinstance(tc, dict) for tc in tool_calls):
                             response_tool_calls = tool_calls
                         else:
                             print(f"Warning: Unexpected tool_calls format in history for msg {i}: {tool_calls}")

                     # If there are tool calls, maybe clear the formatted_content?
                     # Decide if an AI message that *only* calls tools should have empty content.
                     # For now, let's keep content_str but NOT add tool_calls_str to it.
                     formatted_content = content_str # Use only the text content

                 elif isinstance(msg, ToolMessage):
                     sender = "tool_result"
                     node = "tools"
                     tool_name = getattr(msg, 'name', 'unknown_tool')
                     is_error = isinstance(msg.content, Exception)
                     if isinstance(msg.content, str): formatted_content = msg.content
                     elif msg.content is None: formatted_content = ""
                     else:
                         try: formatted_content = json.dumps(msg.content)
                         except TypeError: formatted_content = str(msg.content)

                 if sender and formatted_content is not None:
                     msg_timestamp = base_timestamp_ms + i if base_timestamp_ms is not None else None
                     history_messages.append(HistoryMessage(
                         id=f"{thread_id}-{i}", # Use checkpoint ID (thread_id) in message ID
                         sender=sender,
                         content=formatted_content,
                         timestamp=msg_timestamp,
                         node=node,
                         tool_name=tool_name, # Only relevant for tool_result
                         is_error=is_error, # Relevant for tool_result or system
                         tool_calls=response_tool_calls if sender == 'ai' else None # Add the structured tool_calls
                         # set_id is not typically stored in checkpoint messages, omit or derive if needed
                     ))
             # --- End Message Loop ---

        # Return history with the string thread_id used for lookup
        return HistoryResponse(messages=history_messages, thread_id=thread_id)

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
        print(f"Error getting history for thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load history.")


@app.delete("/api/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread_endpoint(
    thread_id: str = FastApiPath(..., title="The LangGraph thread ID (UUID string) to delete")
):
    """Deletes all checkpoint data associated with a specific thread ID."""
    if not checkpointer:
        print("Error: Checkpointer not available for deleting thread.")
        raise HTTPException(status_code=500, detail="Checkpointer service unavailable.")

    if not isinstance(checkpointer, AsyncSqliteSaver):
        print(f"Error: Checkpointer is not an AsyncSqliteSaver ({type(checkpointer)}), cannot delete thread directly.")
        raise HTTPException(status_code=501, detail="Deletion not supported for this checkpointer type.")

    print(f"Attempting to delete thread ID: {thread_id}")
    try:
        # Assuming the table name is 'checkpoints' as is common with SqliteSaver
        # If using a different saver or custom tables, adjust the table name.
        async with checkpointer.conn.cursor() as cursor:
            # Delete from the main checkpoints table
            await cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            deleted_count = cursor.rowcount
            print(f"Deleted {deleted_count} rows from checkpoints table for thread {thread_id}")

            # Note: If other tables are linked via thread_id (e.g., 'writes'),
            # they might need explicit deletion too, depending on DB schema/constraints.
            # await cursor.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))

        await checkpointer.conn.commit()
        print(f"Successfully deleted data for thread ID: {thread_id}")

        if deleted_count == 0:
            # Optionally, return 404 if the thread didn't exist, although 204 is also acceptable idempotently.
            # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Thread ID '{thread_id}' not found.")
            print(f"Warning: No checkpoint data found for thread ID '{thread_id}' during deletion.")


        # Return No Content on success (even if nothing was deleted)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except aiosqlite.Error as e:
        print(f"Database error deleting thread {thread_id}: {e}")
        traceback.print_exc()
        # Consider rollback if the DB supports it and commit fails partially
        # await checkpointer.conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error deleting thread: {e}")
    except Exception as e:
        print(f"Unexpected error deleting thread {thread_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error deleting thread: {e}")


# --- Wrapper for Streaming with Initial Thread Creation Event ---
async def stream_run_with_creation_event(
    new_thread_id: str, # The newly generated thread_id
    input_messages: List[BaseMessage],
    constitutions: List[Union[ConstitutionRefById, ConstitutionFullText]], # Updated type hint
    run_app: Any
) -> AsyncGenerator[ServerSentEvent, None]:
    """Yields a thread_created event first, then streams the rest."""
    # 1. Yield the initial thread creation event
    created_data = SSEThreadCreatedData(thread_id=new_thread_id)
    sse_payload = SSEEventData(type="thread_created", node="setup", data=created_data)
    yield ServerSentEvent(data=sse_payload.model_dump_json())
    print(f"Sent thread_created event for Thread ID: {new_thread_id}")

    # 2. Yield the rest of the events from the standard stream_events helper
    async for event in stream_events(
        thread_id=new_thread_id, # Use the new_thread_id for the actual run
        input_messages=input_messages,
        constitutions=constitutions, # Pass updated constitutions list
        run_app=run_app,
        set_id=None # Standard stream doesn't use set_id
    ):
        yield event


# --- Run Endpoints ---

@app.post("/api/runs/stream")
async def run_stream_endpoint(request: StreamRunRequest):
    """Handles streaming runs for a single thread (normal chat)."""
    try:
        # 1. Prepare input messages (common step)
        if not request.input or not request.input.content:
             raise HTTPException(status_code=400, detail="Input content is required to start a stream.")
        input_messages = [HumanMessage(content=request.input.content)]

        # 2. Handle new vs. existing thread
        if request.thread_id is None:
            # New thread: Generate ID and use the wrapper stream
            new_thread_id = str(uuid.uuid4())
            print(f"Received request for new thread. Generated Thread ID: {new_thread_id}")
            event_stream = stream_run_with_creation_event(
                new_thread_id=new_thread_id,
                input_messages=input_messages,
                constitutions=request.constitutions, # Pass the new constitutions list
                run_app=graph_app
            )
        else:
            # Existing thread: Use the standard stream_events helper directly
            existing_thread_id = request.thread_id
            print(f"Received request to continue Thread ID: {existing_thread_id}")
            event_stream = stream_events(
                thread_id=existing_thread_id, # Pass the existing thread_id
                input_messages=input_messages,
                constitutions=request.constitutions, # Pass the new constitutions list
                run_app=graph_app
            )

        # 3. Return the appropriate SSE response stream
        return EventSourceResponse(event_stream)

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
        print(f"Error setting up stream run for thread {request.thread_id}: {e}")
        traceback.print_exc()
        # Return an error response instead of EventSourceResponse if setup fails
        raise HTTPException(status_code=500, detail="Failed to initiate stream.")


# --- Compare Streaming Helper and Endpoint ---

async def stream_compare_events(
    base_thread_id: Optional[str], # The base thread ID (UUID string) or None if new
    input_message: BaseMessage,
    constitution_sets: List[CompareRunSet], # Use the Pydantic model directly
    include_inner_agent_only: bool = True # Flag to control inner agent run
) -> AsyncGenerator[ServerSentEvent, None]:
    """Runs multiple streams concurrently for comparison and multiplexes their events."""
    event_queue = asyncio.Queue()
    consumer_tasks = []
    # Tuple now holds: (thread_id, List[Union[ConstitutionRefById, ConstitutionFullText]], set_id, run_app) - Update type hint if CompareRunSet changes
    runs_to_perform: List[Tuple[str, List[Union[ConstitutionRefById, ConstitutionFullText]], str, Any]] = [] 

    # Generate a unique group ID for this comparison operation - currently unused, could be used for logging/grouping
    # compare_group_id = str(uuid.uuid4())

    # Determine base thread ID for naming/grouping checkpoints
    # If starting a new comparison, generate a base UUID, otherwise use the provided one
    effective_base_thread_id = base_thread_id or str(uuid.uuid4())
    is_new_comparison_thread = base_thread_id is None
    print(f"Compare: Base Thread ID: {effective_base_thread_id} (New: {is_new_comparison_thread})")

    # Prepare Superego-involved runs
    for const_set in constitution_sets:
        set_id = const_set.id
        # Create a unique thread ID for this specific run within the comparison
        run_thread_id = f"compare_{effective_base_thread_id}_{set_id}"
        runs_to_perform.append(
            (run_thread_id, const_set.constitutions, set_id, graph_app) # Use const_set.constitutions
        )

    # Prepare Inner Agent Only run (if applicable)
    if include_inner_agent_only and inner_agent_app:
        inner_set_id = "inner_agent_only"
        inner_run_thread_id = f"compare_{effective_base_thread_id}_{inner_set_id}"
        runs_to_perform.append(
            (inner_run_thread_id, [], inner_set_id, inner_agent_app)
        )
    elif include_inner_agent_only:
         print("Warning: Inner agent app not available, skipping inner_agent_only comparison run.")

    active_stream_count = len(runs_to_perform)
    print(f"Compare: Starting {active_stream_count} parallel runs based on Base Thread ID: {effective_base_thread_id}")

    # Launch consumer tasks
    for run_thread_id, constitutions_for_run, set_id, run_app in runs_to_perform:
        print(f"Compare: Launching Set='{set_id}', Thread ID='{run_thread_id}'")
        stream = stream_events(
            thread_id=run_thread_id, # Pass the unique thread ID for this run
            input_messages=[input_message],
            constitutions=constitutions_for_run, # Pass the list of constitution refs (still old type for compare)
            run_app=run_app,
            set_id=set_id # Pass set_id for frontend tracking
        )
        # Need to define consume_and_forward_stream if it's not already defined
        async def consume_and_forward_stream(stream: AsyncGenerator[ServerSentEvent, None], queue: asyncio.Queue):
            """Helper coroutine to consume events from a stream and put them on a queue."""
            try:
                async for event in stream:
                    await queue.put(event)
            except Exception as e:
                print(f"Error consuming stream: {e}")
                # Put an error event on the queue? Or just signal completion?
                # For now, just signal completion via None.
            finally:
                await queue.put(None) # Signal completion

        task = asyncio.create_task(consume_and_forward_stream(stream, event_queue))
        consumer_tasks.append(task)

    # Multiplex events from the queue
    finished_streams = 0
    while finished_streams < active_stream_count:
        try:
            event = await event_queue.get()
            if event is None:
                finished_streams += 1
                continue
            yield event
            event_queue.task_done()
        except asyncio.CancelledError:
             print("Compare event streaming cancelled.")
             break
        except Exception as e:
            print(f"Error processing compare event queue: {e}")
            # Yield a generic error for the comparison itself
            yield ServerSentEvent(data=SSEEventData(
                type="error", node="compare_multiplexer", data=f"Compare error: {e}"
            ).model_dump_json())
            # Signal end with the *base* thread ID so frontend knows the overall operation ended
            yield ServerSentEvent(data=SSEEventData(
                type="end", node="error", data=SSEEndData(thread_id=effective_base_thread_id)
            ).model_dump_json())


    print(f"Compare streaming finished for base Thread ID {effective_base_thread_id}.")
    for task in consumer_tasks:
         if not task.done(): task.cancel()
    await asyncio.gather(*consumer_tasks, return_exceptions=True)


@app.post("/api/runs/compare/stream")
async def run_compare_stream_endpoint(request: CompareRunRequest):
    """Handles streaming runs for comparing multiple constitution sets."""
    base_thread_id = request.thread_id # Use base_thread_id

    try:
        # 1. Validate input
        if not request.input or not request.input.content:
             raise HTTPException(status_code=400, detail="Input content is required for comparison.")
        # Allow empty constitution_sets if inner_agent_app exists
        if not request.constitution_sets and not inner_agent_app:
             raise HTTPException(status_code=400, detail="At least one constitution set (or inner agent) is required for comparison.")

        # 2. Prepare input message
        input_message = HumanMessage(content=request.input.content)

        # 3. Return the SSE response stream
        return EventSourceResponse(stream_compare_events(
            base_thread_id=base_thread_id, # Pass base_thread_id
            input_message=input_message,
            constitution_sets=request.constitution_sets,
            include_inner_agent_only=True # Assuming we always want inner agent if available
        ))

    except HTTPException:
        raise # Re-raise validation or explicit HTTP errors
    except Exception as e:
         print(f"Error setting up compare run for thread {request.thread_id}: {e}")
         traceback.print_exc()
         raise HTTPException(status_code=500, detail="Failed to initiate comparison stream.")


# --- Authentication Endpoints ---

@app.get("/api/auth/google/login")
async def auth_google_login(request: Request):
    """
    Initiates the Google OAuth 2.0 login flow by redirecting the user to Google.
    Stores the OAuth state in the session.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth credentials not configured.")

    # Create the flow instance for the request using from_client_config
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
                "javascript_origins": [FRONTEND_URL.rstrip('/')] # Optional but good practice
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    # Generate the authorization URL and state
    authorization_url, state = flow.authorization_url(
        access_type='offline', # Request refresh token
        include_granted_scopes='true',
        prompt='consent' # Force consent screen for refresh token on first login
    )

    # Store the state in the session to prevent CSRF attacks
    request.session['oauth_state'] = state
    logging.info(f"Redirecting user to Google for login. State: {state}")

    # Redirect the user's browser to Google's authorization page
    return RedirectResponse(authorization_url)


@app.get("/api/auth/google/callback")
async def auth_google_callback(request: StarletteRequest):
    """
    Handles the callback from Google after user authentication.
    Exchanges the authorization code for tokens, fetches user info, creates a JWT,
    sets it as a cookie, and redirects back to the frontend.
    """
    # Check for state mismatch (CSRF protection)
    state = request.session.get('oauth_state')
    if not state or state != request.query_params.get('state'):
        logging.error("OAuth state mismatch or missing state.")
        raise HTTPException(status_code=401, detail="Invalid OAuth state.")
    request.session.pop('oauth_state', None) # Consume the state

    # Check for errors from Google
    error = request.query_params.get('error')
    if error:
        logging.error(f"Google OAuth error: {error}")
        raise HTTPException(status_code=401, detail=f"Google OAuth error: {error}")

    # Get the authorization code from the query parameters
    code = request.query_params.get('code')
    if not code:
        logging.error("Missing authorization code in Google callback.")
        raise HTTPException(status_code=400, detail="Missing authorization code.")

    # Recreate the flow instance using from_client_config
    flow = Flow.from_client_config(
         client_config={
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    try:
        # Exchange the authorization code for credentials (access token, refresh token, etc.)
        logging.info("Exchanging authorization code for tokens...")
        flow.fetch_token(code=code)
        credentials = flow.credentials
        logging.info("Tokens obtained successfully.")

        # Use credentials to get user info (requires requests library)
        # Note: google-auth library can sometimes handle this, but requests is explicit
        userinfo_response = requests.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'}
        )
        userinfo_response.raise_for_status() # Raise exception for bad status codes
        user_info = userinfo_response.json()
        logging.info(f"User info obtained: {user_info.get('email')}")

        # --- User Handling (Example) ---
        # Here you would typically:
        # 1. Check if the user exists in your database based on user_info['email'] or user_info['sub'] (Google ID).
        # 2. If they exist, update their info (e.g., name, picture, last login).
        # 3. If they don't exist, create a new user record.
        # For this example, we'll just use the email in the JWT.
        user_email = user_info.get('email')
        if not user_email:
             raise HTTPException(status_code=500, detail="Could not retrieve user email from Google.")

        # --- Create JWT ---
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_email, "name": user_info.get("name"), "picture": user_info.get("picture")}, # 'sub' (subject) is standard for user ID
            expires_delta=access_token_expires
        )
        logging.info(f"JWT created for user: {user_email}")

        # --- Set Cookie and Redirect ---
        response = RedirectResponse(url=FRONTEND_URL) # Redirect back to the frontend app
        response.set_cookie(
            key="session_token",
            value=access_token,
            httponly=True, # Cookie not accessible via JavaScript
            secure=FRONTEND_URL.startswith("https"), # Send only over HTTPS if frontend is HTTPS
            samesite="lax", # Good default for CSRF protection
            max_age=int(access_token_expires.total_seconds()) # Set cookie expiration
        )
        logging.info(f"Session cookie set. Redirecting to {FRONTEND_URL}")
        return response

    except requests.exceptions.RequestException as e:
        logging.error(f"Network error during token exchange or user info fetch: {e}")
        raise HTTPException(status_code=503, detail="Network error communicating with Google.")
    except Exception as e:
        logging.error(f"Error during Google OAuth callback: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An internal error occurred during authentication: {e}")


# --- Example Protected Endpoint ---
# Dependency to get the current user from the JWT cookie
async def get_current_user(request: Request) -> UserInfo:
    """Dependency to extract and verify JWT from cookie, returning user info."""
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}, # Though we use cookies, this is standard
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        # You could fetch user details from DB here using the email/sub
        user_data = UserInfo(email=email, name=payload.get("name"), picture=payload.get("picture"))
        return user_data
    except JWTError as e: # Use JWTError from jose
        logging.warning(f"JWT validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.get("/api/users/me", response_model=UserInfo)
async def read_users_me(current_user: UserInfo = Depends(get_current_user)):
    """Returns the information of the currently authenticated user."""
    return current_user

@app.post("/api/auth/logout")
async def logout(response: Response):
    """Clears the session token cookie."""
    logging.info("User logging out.")
    response.delete_cookie(key="session_token", httponly=True, secure=FRONTEND_URL.startswith("https"), samesite="lax")
    return {"message": "Successfully logged out"}


# --- Main Execution ---
if __name__ == "__main__":
    import uvicorn
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY environment variable not set. LangGraph models may fail.")

    # Explicitly bind to 127.0.0.1 for testing localhost connection
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    reload = os.getenv("BACKEND_RELOAD", "true").lower() == "true"

    print(f"Starting Uvicorn server on {host}:{port} (Reload: {'enabled' if reload else 'disabled'})")
    uvicorn.run(
        "backend_server_async:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

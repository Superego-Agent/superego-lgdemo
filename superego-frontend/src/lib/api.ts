// src/lib/api.ts
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { nanoid } from 'nanoid';
import {
    getOrCreateConversationForThread,
    findConversationByThreadId,
    managedConversations, // Need this to find clientId from threadId sometimes
    createNewConversation // Added missing import
} from './conversationManager';
import type { ConversationMetadata } from './conversationManager';
import {
    conversationStates,
    activeConversationId,
    globalError,
    availableConstitutions,
    activeConstitutionIds, // Keep for streamRun params, though UI might change
    constitutionAdherenceLevels, // Keep for streamRun params
    ensureConversationStateExists,
    updateConversationState,
    updateConversationMetadataState
} from './stores';
import type { ConversationState } from './stores';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'; 

interface SSEThreadCreatedData {
    thread_id: string;
}
interface SSEEndData {
    thread_id: string;
}
interface SSEEventData {
    type: "thread_created" | "chunk" | "ai_tool_chunk" | "tool_result" | "error" | "end";
    node: string | null;
    data: SSEThreadCreatedData | string | SSEToolCallChunkData | SSEToolResultData | SSEEndData;
    set_id: string | null; // Used for compare mode
}
interface StreamRunInput { type: "human"; content: string; }
interface StreamRunRequest { thread_id?: string | null; input: StreamRunInput; constitution_ids: string[]; adherence_levels_text?: string; }
interface CompareRunRequest { thread_id?: string | null; input: StreamRunInput; constitution_sets: Array<{ id: string; constitution_ids: string[] }>; }


// --- Core API Fetch Helper ---
async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
    globalError.set(null); 

    try {
        const response = await fetch(url, {
            ...options,
            signal, // Pass signal if provided
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers,
            },
        });
        if (!response.ok) {
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try {
                const errorBody = await response.json();
                errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
            } catch (e) { /* Ignore */ }
            throw new Error(errorMsg);
        }
        if (response.status === 204) { // Handle No Content
            return undefined as T;
        }
        return await response.json() as T;
    } catch (error: unknown) {
        // Don't set globalError here for AbortError, let callers handle context-specific errors
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
            console.error('API Fetch Error:', url, error);
            const errorMsg = error instanceof Error ? error.message : String(error);
            globalError.set(errorMsg || 'An unknown API error occurred.'); // Set global error for non-abort errors
            throw error; // Re-throw non-abort errors
        } else {
            console.log('API Fetch aborted:', url);
            throw error; // Re-throw AbortError so callers know
        }
    }
    // Removed finally block that set isLoading
}

// --- API Functions ---

export const fetchConstitutions = async (): Promise<ConstitutionItem[]> => {
    console.log('API: Fetching constitutions');
    // No signal needed usually for this simple fetch
    const constitutions = await apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`);
    availableConstitutions.set(constitutions);
    return constitutions;
};

// Modified fetchHistory to update conversationStates
export const fetchHistory = async (threadId: string, signal: AbortSignal, clientId: string): Promise<void> => {
    console.log(`API: Fetching history for Client ID ${clientId} (Thread ID ${threadId})`);
    // Status is already set to 'loading_history' by the caller (store subscription)
    try {
        const historyData = await apiFetch<HistoryResponse>(`${BASE_URL}/threads/${threadId}/history`, {}, signal);
        // Update state on success
        conversationStates.update(s => {
            if (s[clientId]) {
                s[clientId].messages = historyData.messages || [];
                s[clientId].status = 'idle';
                s[clientId].error = undefined;
            }
            return s;
        });
    } catch (error: unknown) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
            console.error(`API: Failed to fetch history for Client ID ${clientId}:`, error);
            // Update state on error
            conversationStates.update(s => {
                if (s[clientId]) {
                    s[clientId].messages = []; // Clear messages on error
                    s[clientId].status = 'error';
                    s[clientId].error = error instanceof Error ? error.message : String(error);
                }
                return s;
            });
            // Re-throwing might not be necessary if the store subscription handles the error state
        } else {
            console.log(`API: History fetch aborted for Client ID ${clientId}`);
            // State should be updated by the finally block below
        }
        // Do not re-throw AbortError, let the finally block handle cleanup
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
           throw error; // Re-throw other errors if needed by caller, though store handles UI state
        }
    } finally {
        // Always clear the controller and ensure status isn't stuck on loading, even if aborted
        conversationStates.update(s => {
            if (s[clientId]) {
                if (s[clientId].status === 'loading_history') {
                    // If aborted during loading, reset to idle (or error if set above)
                    s[clientId].status = s[clientId].error ? 'error' : 'idle';
                }
                 s[clientId].abortController = undefined; // Clear controller
            }
            return s;
        });
    }
};

// submitConstitution remains largely the same, doesn't interact with conversation state
export const submitConstitution = async (submission: ConstitutionSubmission): Promise<SubmissionResponse> => {
    console.log('API: Submitting constitution');
    return await apiFetch<SubmissionResponse>(`${BASE_URL}/constitutions/submit`, {
        method: 'POST',
        body: JSON.stringify(submission),
    });
};

// cancelStream is removed - cancellation is handled via abortController in conversationStates

// --- SSE Message Processing ---

// Helper to find the client ID based on thread ID or set ID (for compare mode)
function getClientIdForSSE(threadId: string | null, setId: string | null): string | null {
    if (!threadId) {
        console.warn("SSE event received without thread_id, cannot determine client ID.");
        return null;
    }
    // TODO: Adapt for compare mode using setId if necessary
    const conversation = findConversationByThreadId(threadId);
    if (!conversation) {
        console.warn(`SSE event for unknown thread_id ${threadId}, cannot determine client ID.`);
        // This might happen if the thread_created event hasn't been processed yet
        // or if metadata wasn't created properly.
        return null;
    }
    return conversation.id;
}


// SSE Handlers now update conversationStates via clientId
// Note: currentMsgs parameter is removed, we get/update state via clientId

function _handleChunk(clientId: string, data: string, nodeId: string | null, setId: string | null): void {
    const chunkContent = data;
    if (chunkContent === null || chunkContent === undefined) return;

    conversationStates.update(s => {
        const state = s[clientId];
        if (!state) return s; // Should not happen if clientId is valid

        const lastMsgIndex = state.messages.length - 1;
        const lastMessage = lastMsgIndex >= 0 ? state.messages[lastMsgIndex] : null;

        // Append chunk to the last AI message if it matches node/set and is streaming
        // Using lastProcessedNodeId might be less reliable here, better to check last message type/node
        if (lastMessage?.sender === 'ai' && (lastMessage.node ?? null) === nodeId /* && state.status === 'streaming' */ ) {
             // Ensure content exists before appending
             const currentContent = lastMessage.content || '';
             state.messages[lastMsgIndex] = { ...lastMessage, content: currentContent + chunkContent };
        } else {
            // Create new AI message
            const newMsg: AIMessage = { id: nanoid(8), sender: 'ai', content: chunkContent, node: nodeId, set_id: setId ?? null, timestamp: Date.now(), tool_calls: [] };
            state.messages = [...state.messages, newMsg]; // Svelte reactivity: Use assignment
        }
        state.status = 'streaming'; // Ensure status is streaming
        return s;
    });
}

function _handleToolChunk(clientId: string, data: SSEToolCallChunkData, nodeId: string | null, setId: string | null): void {
     conversationStates.update(s => {
        const state = s[clientId];
        if (!state) return s;

        // Find last matching AI message in this conversation's state
        let targetAiMsgIndexTool = -1;
        for (let i = state.messages.length - 1; i >= 0; i--) {
            const msg = state.messages[i];
            if (msg.sender === 'ai' && (msg.node ?? null) === nodeId) {
                 if (!setId || (msg.set_id ?? null) === setId) { targetAiMsgIndexTool = i; break; }
            }
        }

        // If no matching AI message found for this node/set, create one.
        if (targetAiMsgIndexTool === -1) {
            console.log(`_handleToolChunk: No existing AI message for node ${nodeId}, set ${setId}. Creating one.`);
            const newMsg: AIMessage = {
                id: nanoid(8),
                sender: 'ai',
                content: "", // Start with empty content
                node: nodeId,
                set_id: setId ?? null,
                timestamp: Date.now(),
                tool_calls: [] // Initialize tool calls array
            };
            state.messages = [...state.messages, newMsg]; // Svelte reactivity: Use assignment
            targetAiMsgIndexTool = state.messages.length - 1; // Point to the newly created message
        }

        // Now we are guaranteed to have a target message index
        let targetMsg = state.messages[targetAiMsgIndexTool] as AIMessage;
         if (!targetMsg.tool_calls) {
             targetMsg.tool_calls = [];
         }

         // --- Refined Logic for Tool Chunk Handling & Reactivity ---
         let newToolCalls: ToolCall[]; // Declare variable for the final tool_calls array

         if (data.name) {
             // Initial chunk: Create new tool call and add it to the existing ones.
             const newToolCall: ToolCall = {
                 id: data.id || nanoid(6),
                 name: data.name,
                 args: data.args || ""
             };
             newToolCalls = [...targetMsg.tool_calls, newToolCall];
         } else if (data.args) {
             // Subsequent chunk: Append args to the last tool call.
             const lastCallIndex = targetMsg.tool_calls.length - 1;
             if (lastCallIndex >= 0) {
                 const lastCall = targetMsg.tool_calls[lastCallIndex];
                 const updatedCall = {
                     ...lastCall,
                     args: (lastCall.args || "") + (data.args || "")
                 };
                 // Create the new array with the updated last call
                 newToolCalls = [
                     ...targetMsg.tool_calls.slice(0, lastCallIndex),
                     updatedCall
                 ];
             } else {
                 // Args chunk arrived before the initial name chunk (shouldn't happen with correct backend stream)
                 console.warn("Received tool args chunk but no existing tool call found.", { clientId, data });
                 newToolCalls = targetMsg.tool_calls; // Keep original array if error
             }
         } else {
             // Chunk with no name or args
             console.warn("Received ai_tool_chunk with no name or args.", { clientId, data });
             newToolCalls = targetMsg.tool_calls; // Keep original array
         }

         // Create a completely new message object with the new tool_calls array
         const updatedMessage = {
             ...targetMsg,
             tool_calls: newToolCalls // Assign the newly constructed array
         };

         // Assign the new message object back into the state's messages array
         state.messages[targetAiMsgIndexTool] = updatedMessage;
         // --- End Refined Logic ---

         state.status = 'streaming'; // Ensure status is streaming
        return s;
    });
}

function _handleToolResult(clientId: string, data: SSEToolResultData, nodeId: string | null, setId: string | null): void {
    const newToolResultMsg: ToolResultMessage = { id: nanoid(8), sender: 'tool_result', content: data.result, tool_name: data.tool_name, is_error: data.is_error, node: nodeId, set_id: setId ?? null, timestamp: Date.now(), tool_call_id: data.tool_call_id };
    conversationStates.update(s => {
        if (s[clientId]) {
            s[clientId].messages = [...s[clientId].messages, newToolResultMsg]; // Svelte reactivity: Use assignment
            s[clientId].status = 'streaming'; // Still streaming until 'end'
        }
        return s;
    });
}

function _handleError(clientId: string | null, data: string, nodeId: string | null, setId: string | null): void {
    console.error(`SSE Error Event (Client: ${clientId}, Node: ${nodeId}, Set: ${setId}):`, data);
    const errorContent = `Error (node: ${nodeId || 'graph'}, set: ${setId || 'general'}): ${data}`;
    const newErrorMsg: SystemMessage = { id: nanoid(8), sender: 'system', content: errorContent, node: nodeId, set_id: setId ?? null, isError: true, timestamp: Date.now() };

    if (clientId) {
        conversationStates.update(s => {
            if (s[clientId]) {
                s[clientId].messages = [...s[clientId].messages, newErrorMsg]; // Svelte reactivity: Use assignment
                s[clientId].status = 'error'; // Set status to error
                s[clientId].error = data; // Store error message
                s[clientId].abortController = undefined; // Clear controller on error
            }
            return s;
        });
    } else {
        // If we can't identify the client, report as global error
        globalError.set(errorContent);
    }
}

// Modified _handleThreadCreated to update the *initiating* conversation
// It needs the clientId associated with the stream where this event arrived.
function _handleThreadCreated(clientId: string, data: SSEThreadCreatedData, nodeId: string | null, setId: string | null): void {
    const { thread_id: newThreadId } = data;
    if (!clientId) {
        console.error("SSE 'thread_created': Cannot process without the client ID of the initiating stream.");
        globalError.set("Internal error processing new conversation start.");
        return;
    }
    if (typeof newThreadId === 'string' && newThreadId) {
        console.log(`SSE thread_created: Associating backend thread ${newThreadId} with Client ID ${clientId}`);
        try {
            // 1. Update the metadata in managedConversations (persists to localStorage)
            managedConversations.update(list =>
                list.map(conv =>
                    conv.id === clientId ? { ...conv, thread_id: newThreadId, last_updated_at: new Date().toISOString() } : conv
                ).sort((a, b) => new Date(b.last_updated_at).getTime() - new Date(a.last_updated_at).getTime())
            );

            // 2. Update the metadata and status within conversationStates store
            conversationStates.update(s => {
                 if (s[clientId]) {
                     s[clientId].metadata.thread_id = newThreadId; // Assign the backend ID
                     s[clientId].status = 'streaming'; // Ensure status is streaming
                     s[clientId].error = undefined;
                 } else {
                      console.error(`SSE 'thread_created': State for initiating client ID ${clientId} not found!`);
                      // Attempt recovery? Or rely on ensureConversationStateExists having run?
                 }
                 return s;
            });

            // 3. DO NOT change activeConversationId here. It was already set correctly by streamRun.
            console.log(`SSE thread_created: Updated state for Client ID ${clientId} with Thread ID ${newThreadId}.`);

        } catch (error: unknown) {
             console.error(`SSE thread_created: Failed to update state for Client ID ${clientId} with thread ${newThreadId}:`, error);
             globalError.set(`Failed to update chat state: ${error instanceof Error ? error.message : String(error)}`);
        }
    } else {
        console.error(`SSE 'thread_created': Event received for Client ID ${clientId} without valid thread_id:`, data);
        globalError.set("Received invalid conversation data from server.");
        // Set error state for the specific conversation
         conversationStates.update(s => {
             if(s[clientId]) {
                 s[clientId].status = 'error';
                 s[clientId].error = 'Invalid thread data from server.';
                 s[clientId].abortController = undefined;
             }
             return s;
         });
    }
}

function _handleEnd(clientId: string | null, data: SSEEndData, nodeId: string | null, setId: string | null): void {
    const { thread_id: endedThreadId } = data;
    console.log(`SSE Stream ended (Client: ${clientId}, Node: ${nodeId}, Set: ${setId}, Backend Thread: ${endedThreadId})`);

    if (clientId) {
        conversationStates.update(s => {
            if (s[clientId]) {
                // Only set to idle if currently streaming, otherwise preserve error state etc.
                if (s[clientId].status === 'streaming') {
                    s[clientId].status = 'idle';
                }
                s[clientId].abortController = undefined; // Clear controller on end
            }
            return s;
        });
    } else {
         console.warn(`SSE 'end' event received for unknown client.`);
    }
}

// --- Central SSE Message Router ---
// Needs clientId to route updates correctly
function handleSSEMessage(event: EventSourceMessage, clientId: string | null) { // Added clientId parameter
    try {
        if (!event.data) { console.warn('SSE message received with no data.'); return; }
        const parsedData: SSEEventData = JSON.parse(event.data);
        const setId = parsedData.set_id ?? null;
        const currentNodeId = parsedData.node ?? null;
        const type = parsedData.type;
        const eventData = parsedData.data;
        let targetClientId = clientId; // Use the clientId passed from performStreamRequest

        // Special handling for thread_created - needs the clientId of the stream it arrived on
        if (type === 'thread_created') {
             // Pass the stream's clientId
            _handleThreadCreated(targetClientId!, eventData as SSEThreadCreatedData, currentNodeId, setId);
            return;
        }

        // For other events, if clientId wasn't passed (shouldn't happen anymore), try to find it
        if (!targetClientId && type !== 'error') {
             console.warn(`SSE event type '${type}' received without pre-associated clientId. Attempting lookup...`);
             const threadId = (eventData as SSEEndData)?.thread_id; // Only 'end' reliably has thread_id here
             if (threadId) {
                 targetClientId = getClientIdForSSE(threadId, setId);
             }
        }

        if (!targetClientId && type !== 'error') {
            console.warn(`Cannot handle SSE event type '${type}' without a client ID. Waiting for 'thread_created'?`, parsedData);
            return;
        }

          // Route to specific handlers
          switch (type) {
              case 'chunk':
                  _handleChunk(targetClientId!, eventData as string, currentNodeId, setId);
                  break;
              case 'ai_tool_chunk':
                  _handleToolChunk(targetClientId!, eventData as SSEToolCallChunkData, currentNodeId, setId);
                  break;
              case 'tool_result':
                _handleToolResult(targetClientId!, eventData as SSEToolResultData, currentNodeId, setId);
                break;
            case 'error':
                // Handle error even if clientId is uncertain, report globally if needed
                _handleError(targetClientId, eventData as string, currentNodeId, setId);
                break;
            case 'end':
                _handleEnd(targetClientId, eventData as SSEEndData, currentNodeId, setId);
                break;
            default:
                console.warn('Unhandled SSE event type:', type);
        }

    } catch (error: unknown) {
        console.error('Failed to parse or handle SSE message data:', event.data, error);
        globalError.set(`Error processing message from server: ${error instanceof Error ? error.message : String(error)}`);
        // Attempt to set error state on active conversation if possible
        const activeId = get(activeConversationId);
        if (activeId) {
             conversationStates.update(s => {
                 if(s[activeId]) {
                     s[activeId].status = 'error';
                     s[activeId].error = 'Failed to process server message.';
                     s[activeId].abortController = undefined;
                 }
                 return s;
             });
        }
    }
}

// --- Stream Request Orchestration ---
// Modified to manage AbortController in conversationStates
async function performStreamRequest(
    endpoint: string,
    requestBody: StreamRunRequest | CompareRunRequest,
    clientId: string // Expect clientId to be passed in
): Promise<void> {
    console.log(`API: Connecting to ${BASE_URL}${endpoint} for Client ID: ${clientId}`);
    globalError.set(null); // Clear global error at start of new stream

    const controller = new AbortController();

    // Store the controller in the conversation state
    conversationStates.update(s => {
        if (s[clientId]) {
            // Abort any existing controller for this client first
            s[clientId].abortController?.abort();
            s[clientId].abortController = controller;
            s[clientId].status = 'streaming'; // Set status to streaming
            s[clientId].error = undefined; // Clear previous error
        } else {
            // This case should ideally be handled before calling performStreamRequest
            // e.g., ensureConversationStateExists called first
            console.error(`API: State for Client ID ${clientId} not found before starting stream!`);
            // Initialize a minimal state? Or throw error?
             s[clientId] = {
                 metadata: { id: clientId, name: "Loading...", thread_id: requestBody.thread_id ?? null, created_at: new Date().toISOString(), last_updated_at: new Date().toISOString(), last_used_constitution_ids: [] },
                 messages: [],
                 status: 'streaming',
                 abortController: controller
             };
        }
        return s;
    });


    try {
        await fetchEventSource(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
            body: JSON.stringify(requestBody),
            signal: controller.signal,
            openWhenHidden: true, // Keep connection active in background tabs
            onopen: async (response) => {
                if (!response.ok) {
                    let errorMsg = `SSE connection failed! Status: ${response.status}`;
                    try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ }
                    // Update state on connection error
                    conversationStates.update(s => {
                        if (s[clientId]) {
                            s[clientId].status = 'error';
                            s[clientId].error = errorMsg;
                            s[clientId].abortController = undefined;
                        }
                        return s;
                    });
                    throw new Error(errorMsg); // Throw to be caught below
                }
                console.log(`SSE stream opened (${endpoint}) for Client ID: ${clientId}`);
            },
            onmessage: (event) => {
                // Pass clientId to the handler
                handleSSEMessage(event, clientId);
            },
            onclose: () => {
                console.log(`SSE stream closed (${endpoint}) for Client ID: ${clientId}.`);
                // State should be updated to 'idle' or 'error' by 'end' or 'error' events.
                // Clear controller just in case 'end'/'error' didn't fire.
                 conversationStates.update(s => {
                    if (s[clientId]?.abortController === controller) { // Check if it's still the same controller
                         if (s[clientId].status === 'streaming') { // If still streaming, means abnormal close
                             console.warn(`SSE stream closed unexpectedly for ${clientId}. Setting status to idle.`);
                             s[clientId].status = 'idle';
                         }
                         s[clientId].abortController = undefined;
                    }
                    return s;
                });
            },
            onerror: (err) => {
                // fetch-event-source handles aborts gracefully, check if it's a real error
                 if (controller.signal.aborted) {
                     console.log(`Stream intentionally aborted for Client ID: ${clientId}.`);
                     // State cleanup should happen where abort was called or in finally block
                     return; // Don't treat abort as an error
                 }

                console.error(`SSE stream error (${endpoint}) for Client ID ${clientId}:`, err);
                const errorMsg = err instanceof Error ? err.message : String(err);
                globalError.set(`Stream connection error: ${errorMsg}`); // Set global for connection issues
                // Update specific conversation state
                conversationStates.update(s => {
                    if (s[clientId]) {
                        s[clientId].status = 'error';
                        s[clientId].error = `Stream error: ${errorMsg}`;
                        s[clientId].abortController = undefined;
                    }
                    return s;
                });
                // Don't re-throw, allow graceful closure if possible
            },
        });
    } catch (error: unknown) {
         // Catch errors from fetchEventSource setup or onopen failure
         if (!(error instanceof DOMException && error.name === 'AbortError')) {
            console.error(`Stream setup (${endpoint}) failed for Client ID ${clientId}:`, error);
            const errorMsg = error instanceof Error ? error.message : String(error);
             if (!get(globalError)) { // Avoid overwriting more specific errors
                 globalError.set(`Stream setup failed: ${errorMsg}`);
             }
             // Ensure state reflects the error
             conversationStates.update(s => {
                 if (s[clientId]) {
                     if (s[clientId].status !== 'error') { // Don't overwrite specific SSE errors
                         s[clientId].status = 'error';
                         s[clientId].error = `Stream setup failed: ${errorMsg}`;
                     }
                     s[clientId].abortController = undefined;
                 }
                 return s;
             });
        } else {
             console.log(`Stream setup aborted for Client ID: ${clientId}.`);
             // State cleanup should happen where abort was called
        }
    }
}

// --- Public API Functions ---

// Modified streamRun
export const streamRun = async (
    userInput: string,
    currentClientId: string | null, // Expect client ID now, null if starting completely fresh
    constitutionIds: string[] = [],
    adherenceLevelsText?: string
): Promise<void> => {

    let clientId = currentClientId;
    let threadId: string | null = null;

    // Determine thread_id and ensure state exists
    if (clientId) {
        const state = get(conversationStates)[clientId];
        if (state) {
            threadId = state.metadata.thread_id;
            console.log(`API: streamRun called for existing Client ID ${clientId} (Thread ID: ${threadId})`);
        } else {
            console.error(`API: streamRun called with non-existent clientId ${clientId}. This shouldn't happen.`);
            globalError.set(`Cannot send message: Invalid conversation state.`);
            return; // Prevent API call
        }
    } else {
        // This is a brand new chat, started without even a local metadata entry yet.
        // Create local metadata first.
        const newConversation = createNewConversation(); // Creates metadata in localStorage via managedConversations
        clientId = newConversation.id;
        ensureConversationStateExists(newConversation); // Create the state entry in conversationStates
        activeConversationId.set(clientId); // Make it active
        threadId = null; // No backend thread yet
        console.log(`API: streamRun called for new chat. Created Client ID ${clientId}. No Thread ID yet.`);

        // Add optimistic update *only* for this new chat case
        const userMessage: HumanMessage = { id: nanoid(8), sender: 'human', content: userInput, timestamp: Date.now() };
        conversationStates.update(s => {
            if (s[clientId!]) { // clientId is guaranteed to be set here
                s[clientId!].messages = [...s[clientId!].messages, userMessage]; // Svelte reactivity: Use assignment
            }
            return s;
        });
    }

    // Optimistic update for existing chats is handled in ChatInterface.svelte


    const requestBody: StreamRunRequest = {
        thread_id: threadId ?? undefined, // Send thread_id only if it exists
        input: { type: 'human', content: userInput },
        constitution_ids: constitutionIds.length > 0 ? constitutionIds : ['none'],
        adherence_levels_text: adherenceLevelsText || undefined
    };

    // Pass the confirmed clientId to performStreamRequest
    // Add assertion as clientId is guaranteed to be a string here by the logic flow
    await performStreamRequest('/runs/stream', requestBody, clientId!);
};

// fetchConstitutionContent remains the same
export const fetchConstitutionContent = async (constitutionId: string): Promise<string> => {
    console.log(`API: Fetching content for constitution ${constitutionId}`);
    const url = `${BASE_URL}/constitutions/${constitutionId}/content`;
    try {
        const response = await fetch(url, { headers: { 'Accept': 'text/plain', }, });
        if (!response.ok) {
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try { const errorText = await response.text(); errorMsg += ` - ${errorText}`; } catch (e) { /* Ignore */ }
            throw new Error(errorMsg);
        }
        return await response.text();
    } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        console.error(`API Fetch Error (Content): ${url}`, error);
        globalError.set(errorMsg || `Failed to load content for ${constitutionId}.`);
        throw error;
    }
};

// streamCompareRun needs similar refactoring if/when implemented fully
export const streamCompareRun = async (
    userInput: string,
    threadId: string | null, // Base thread ID or null
    compareSetsConfig: CompareSet[]
): Promise<void> => {
    // TODO: Refactor streamCompareRun
    // - Determine/create parent compare_session clientId
    // - Create state entries for each leg in conversationStates
    // - Pass relevant info (parent clientId, leg set_ids) to performStreamRequest
    // - performStreamRequest needs modification to handle compare endpoint specifics
    // - SSE handlers need modification to route based on set_id to the correct leg state
    console.warn("streamCompareRun not fully refactored for new state model yet.");

    const requestBody: CompareRunRequest = {
        thread_id: threadId ?? undefined,
        input: { type: 'human', content: userInput },
        constitution_sets: compareSetsConfig.map(set => ({ id: set.id, constitution_ids: set.constitution_ids }))
    };
    console.log(`API: streamCompareRun called for ${threadId ? `Base Thread ID ${threadId}` : 'new comparison base'}.`);
    // await performStreamRequest('/runs/compare/stream', requestBody, /* Need clientId */);
};

// deleteThread remains the same - operates on backend thread_id
export const deleteThread = async (threadId: string): Promise<void> => {
    console.log(`API: Deleting thread ${threadId}`);
    // Use apiFetch helper, expecting 204 No Content on success
    // No signal needed for simple delete
    await apiFetch<void>(`${BASE_URL}/threads/${threadId}`, {
        method: 'DELETE',
    });
    console.log(`API: Successfully requested deletion for thread ${threadId}`);
};

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
    constitutionAdherenceLevels, // Need this to get selected constitutions & check if an ID is global
    ensureConversationStateExists,
    updateConversationState,
    updateConversationMetadataState
    // Removed duplicate imports for constitutionAdherenceLevels and availableConstitutions
} from './stores';
import { localConstitutionsStore } from './localConstitutions'; // Import local store
import { logExecution } from './utils';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';


// --- Core API Fetch Helper ---
async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
    globalError.set(null);

    try {
        // Ensure credentials ('include') is always set for sending cookies
        const fetchOptions: RequestInit = {
            credentials: 'include', // Crucial for sending session_token cookie
            ...options,
            signal, // Pass signal if provided
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers,
            },
        };

        const response = await fetch(url, fetchOptions);
        // Removed console.log(`[apiFetch] Received response...`)
        if (!response.ok) {
            // Removed console.log(`[apiFetch] Response not OK...`)
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try {
                // Attempt to read error body as text first, more robust than assuming JSON
                const errorText = await response.text();
                // Removed console.log(`[apiFetch] Error response body...`)
                try {
                    // Try parsing as JSON if possible for more detail
                    const errorBody = JSON.parse(errorText);
                    errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
                } catch (parseError) {
                    errorMsg += ` - ${errorText}`; // Fallback to raw text
                }
                // Removed original response.json() call here as errorText is now primary
            } catch (e) {
                // Removed console.error(`[apiFetch] Error reading error response body...`)
                // errorMsg already contains status
            }
            throw new Error(errorMsg);
        }
        if (response.status === 204) { // Handle No Content
            // Removed console.log(`[apiFetch] Received 204...`)
            return undefined as T;
        }
        // Removed console.log(`[apiFetch] Attempting to parse JSON...`)
        const jsonData = await response.json() as T;
        // Removed console.log(`[apiFetch] Successfully parsed JSON...`)
        return jsonData;
    } catch (error: unknown) {
        // Removed console.error(`[apiFetch] Caught error...`)
        // Don't set globalError here for AbortError, let callers handle context-specific errors
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
            console.error('API Fetch Error:', url, error); // Keep original console.error for actual fetch errors
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

export const fetchConstitutions = (): Promise<ConstitutionItem[]> => {
    return logExecution("Fetch constitutions", async () => {
        const fullUrl = `${BASE_URL}/constitutions`;
        // Removed console.log(`[fetchConstitutions] Attempting...`)
        try {
            const constitutions = await apiFetch<ConstitutionItem[]>(fullUrl);
            // Removed console.log(`[fetchConstitutions] Successfully fetched...`)
            availableConstitutions.set(constitutions);
            return constitutions;
        } catch (error) {
            // Removed console.error(`[fetchConstitutions] Error during apiFetch...`)
            // logExecution will log the error from apiFetch if it's thrown
            throw error; // Re-throw error for logExecution and Promise.all handling
        }
    });
};

// fetchHistory is called from the store subscription, which uses logExecution.
// We keep internal logging for state updates but remove the outer log.
export const fetchHistory = async (threadId: string, signal: AbortSignal, clientId: string): Promise<void> => {
    // Status is set to 'loading_history' by the caller (store subscription)
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
            // AbortError is handled by the caller (store subscription)
        }
        // Re-throw non-abort errors so the caller's logExecution catches them
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
           throw error;
        }
    } finally {
        // Always clear the controller and ensure status isn't stuck on loading,
        // even if aborted or errored.
        conversationStates.update(s => {
            if (s[clientId]) {
                // If status is still loading_history, reset based on whether an error was set.
                if (s[clientId].status === 'loading_history') {
                    s[clientId].status = s[clientId].error ? 'error' : 'idle';
                }
                s[clientId].abortController = undefined; // Clear controller
            }
            return s;
        });
    }
};

export const submitConstitution = (submission: ConstitutionSubmission): Promise<SubmissionResponse> => {
    return logExecution("Submit constitution", () =>
        apiFetch<SubmissionResponse>(`${BASE_URL}/constitutions/submit`, {
            method: 'POST',
            body: JSON.stringify(submission),
        })
    );
};


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
        console.error("SSE 'thread_created': Cannot process without the client ID."); // Keep error log
        globalError.set("Internal error processing new conversation start.");
        return;
    }
    if (typeof newThreadId === 'string' && newThreadId) {
        try {
            // 1. Update metadata in managedConversations
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

            // 3. Active ID is already set by streamRun.

        } catch (error: unknown) {
             console.error(`SSE thread_created: Failed to update state for Client ID ${clientId} with thread ${newThreadId}:`, error); // Keep error log
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
// Manages AbortController via conversationStates and wraps execution for logging.
async function performStreamRequest(
    endpoint: string,
    requestBody: StreamRunRequest | CompareRunRequest,
    clientId: string
): Promise<void> {
    globalError.set(null); // Clear global error at start

    const controller = new AbortController();

    // Store the controller in the conversation state, aborting previous if necessary
    conversationStates.update(s => {
        if (s[clientId]) {
            s[clientId].abortController?.abort();
            s[clientId].abortController = controller;
            s[clientId].status = 'streaming';
            s[clientId].error = undefined;
        } else {
            // This case should be handled before calling performStreamRequest, but initialize defensively.
            console.error(`API: State for Client ID ${clientId} not found before starting stream! Initializing.`); // Keep error log
             s[clientId] = {
                 metadata: { id: clientId, name: "Loading...", thread_id: requestBody.thread_id ?? null, created_at: new Date().toISOString(), last_updated_at: new Date().toISOString(), last_used_constitution_ids: [] },
                 messages: [],
                 status: 'streaming',
                 abortController: controller
             };
        }
        return s;
    });

    // Wrap the fetchEventSource setup in logExecution
    return logExecution(`Stream request to ${endpoint} for ${clientId}`, async () => {
        // This try/catch block handles errors during the fetchEventSource setup
        // or errors explicitly thrown from within the callbacks (like onopen).
        try {
            await fetchEventSource(`${BASE_URL}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
                body: JSON.stringify(requestBody),
                signal: controller.signal,
                openWhenHidden: true,
                onopen: async (response) => {
                    if (!response.ok) {
                        let errorMsg = `SSE connection failed! Status: ${response.status}`;
                        try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ }
                        conversationStates.update(s => { // Update state on connection error
                            if (s[clientId]) { s[clientId].status = 'error'; s[clientId].error = errorMsg; s[clientId].abortController = undefined; } return s;
                        });
                        throw new Error(errorMsg); // Throw to be caught by outer try/catch -> logExecution
                    }
                },
                onmessage: (event) => {
                    handleSSEMessage(event, clientId);
                },
                onclose: () => {
                    // Clear controller as a fallback if 'end'/'error' didn't fire before close.
                     conversationStates.update(s => {
                        if (s[clientId]?.abortController === controller) {
                             if (s[clientId].status === 'streaming') {
                                 console.warn(`SSE stream closed unexpectedly for ${clientId}. Setting status to idle.`); // Keep this warning
                                 s[clientId].status = 'idle';
                             }
                             s[clientId].abortController = undefined;
                        }
                        return s;
                    });
                },
                onerror: (err) => {
                     if (controller.signal.aborted) { return; } // Don't treat abort as error
                    console.error(`SSE stream error (${endpoint}) for Client ID ${clientId}:`, err); // Keep specific SSE error log
                    const errorMsg = err instanceof Error ? err.message : String(err);
                    globalError.set(`Stream connection error: ${errorMsg}`);
                    conversationStates.update(s => { // Update specific conversation state
                        if (s[clientId]) { s[clientId].status = 'error'; s[clientId].error = `Stream error: ${errorMsg}`; s[clientId].abortController = undefined; } return s;
                    });
                    // Don't throw from onerror, allow graceful closure. Error state is set.
                },
            });
        } catch (error) {
            // This catches errors from fetchEventSource setup or the explicit throw in onopen.
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                 // Ensure state reflects the error if not already set by onerror/onopen
                 conversationStates.update(s => {
                     if (s[clientId] && s[clientId].status !== 'error') {
                         s[clientId].status = 'error';
                         s[clientId].error = `Stream setup failed: ${error instanceof Error ? error.message : String(error)}`;
                         s[clientId].abortController = undefined;
                     }
                     return s;
                 });
            }
            // Re-throw non-abort errors so logExecution knows it failed.
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                 throw error;
            }
        }
    });
}

// --- Public API Functions ---

// Modified streamRun
export const streamRun = async (
    userInput: string,
    currentClientId: string | null // Expect client ID now, null if starting completely fresh
    // Removed constitutionIds and adherenceLevelsText parameters
): Promise<void> => {

    let clientId = currentClientId;
    let threadId: string | null = null;

    // Determine thread_id and ensure state exists
    if (clientId) {
        const state = get(conversationStates)[clientId];
        if (state) {
            threadId = state.metadata.thread_id;
        } else {
            console.error(`API: streamRun called with non-existent clientId ${clientId}.`); // Keep error log
            globalError.set(`Cannot send message: Invalid conversation state.`);
            return; // Prevent API call
        }
    } else {
        // This is a brand new chat, started without even a local metadata entry yet.
        // Create local metadata first.
        const newConversation = createNewConversation(); // Creates metadata in localStorage via managedConversations
        clientId = newConversation.id;
        ensureConversationStateExists(newConversation); // Ensure state entry is created
        activeConversationId.set(clientId); // Make it active
        threadId = null; // No backend thread yet

        // Add user message optimistically *only* when creating a new chat locally
        const userMessage: HumanMessage = { id: nanoid(8), sender: 'human', content: userInput, timestamp: Date.now() };
        conversationStates.update(s => {
            if (s[clientId!]) { // clientId is guaranteed to be set here
                s[clientId!].messages = [...s[clientId!].messages, userMessage]; // Svelte reactivity: Use assignment
            }
            return s;
        });
    }

    // Optimistic update for existing chats is handled in ChatInterface.svelte

    // --- Build the constitutions array for the request ---
    const selectedConstitutionsMap = get(constitutionAdherenceLevels);
    const localConstitutions = get(localConstitutionsStore);
    const globalConstitutions = get(availableConstitutions);

    // Use the new SelectedConstitution type from global.d.ts
    const constitutionsForRequest: SelectedConstitution[] = Object.keys(selectedConstitutionsMap)
        .map(id => {
            const adherenceLevel = selectedConstitutionsMap[id]; // Get the adherence level
            if (!adherenceLevel || adherenceLevel < 1 || adherenceLevel > 5) {
                console.warn(`Invalid adherence level (${adherenceLevel}) for constitution ID "${id}". Skipping.`);
                return null; // Skip if adherence level is invalid
            }

            // Check if it's a local constitution first
            const localMatch = localConstitutions.find(c => c.id === id);
            if (localMatch) {
                // Send title, text, and adherence level for local
                return { title: localMatch.title, text: localMatch.text, adherence_level: adherenceLevel };
            }

            // Check if it's a known global constitution
            const globalMatch = globalConstitutions.find(c => c.id === id);
            if (globalMatch) {
                 // Send id, title, and adherence level for global
                return { id: globalMatch.id, title: globalMatch.title, adherence_level: adherenceLevel };
            }

            // If it's neither (e.g., 'none' or an orphaned ID), log a warning and skip
            // The 'none' constitution should have id 'none' and won't be found in local/global lists.
            if (id !== 'none') { // Don't warn for the special 'none' ID if it's selected
                 console.warn(`Selected constitution ID "${id}" not found in local or global lists. Skipping.`);
            }
            return null;
        })
        .filter(ref => ref !== null); // Filter out nulls - TS should infer the correct type after this

    // Handle the 'none' case explicitly - if 'none' is selected, send an empty array
    // (The backend should handle an empty array appropriately, assuming 'none' means no constitution)
    if (constitutionsForRequest.length === 0 && selectedConstitutionsMap['none']) {
        // If 'none' was the only thing selected, the array is already empty, which is correct.
    } else if (constitutionsForRequest.length > 0 && selectedConstitutionsMap['none']) {
        // If 'none' is selected alongside others, filter it out (it shouldn't be selectable with others anyway, but defensively handle)
        console.warn("Constitution 'none' selected alongside other constitutions. Ignoring 'none'.");
        // The filter logic above already handles this by not finding 'none' in local/global lists.
    }


    const requestBody: StreamRunRequest = {
        thread_id: threadId ?? undefined, // Send thread_id only if it exists
        input: { type: 'human', content: userInput },
        constitutions: constitutionsForRequest // Use the constructed array
        // Removed adherence_levels_text
    };

    // Pass the confirmed clientId to performStreamRequest
    await performStreamRequest('/runs/stream', requestBody, clientId);
};

export const fetchConstitutionContent = (constitutionId: string): Promise<string> => {
    const url = `${BASE_URL}/constitutions/${constitutionId}/content`;
    // Wrap the raw fetch call for logging, handle non-JSON response
    return logExecution(`Fetch constitution content for ${constitutionId}`, async () => {
        try {
            const response = await fetch(url, { headers: { 'Accept': 'text/plain' } });
            if (!response.ok) {
                let errorMsg = `HTTP error! Status: ${response.status}`;
                try { const errorText = await response.text(); errorMsg += ` - ${errorText}`; } catch (e) { /* Ignore */ }
                throw new Error(errorMsg);
            }
            return await response.text();
        } catch (error: unknown) {
            // Set global error specifically for content fetch failure
            globalError.set(error instanceof Error ? error.message : `Failed to load content for ${constitutionId}.`);
            throw error; // Re-throw for logExecution
        }
    });
};

// TODO: Refactor streamCompareRun similarly if implemented
export const streamCompareRun = async (
    userInput: string,
    threadId: string | null,
    compareSetsConfig: CompareSet[]
): Promise<void> => {
    // TODO: Refactor streamCompareRun
    // - Determine/create parent compare_session clientId
    // - Create state entries for each leg in conversationStates
    // - Pass relevant info (parent clientId, leg set_ids) to performStreamRequest
    // - performStreamRequest needs modification to handle compare endpoint specifics
    // - SSE handlers need modification to route based on set_id to the correct leg state
    console.warn("streamCompareRun not fully implemented or refactored yet.");
    // Placeholder for implementation
    // Needs logic to manage compare session state, likely involving multiple clientIds or a parent session ID.
    // const requestBody: CompareRunRequest = { ... };
    // await performStreamRequest('/runs/compare/stream', requestBody, /* ??? */);
};

export const deleteThread = (threadId: string): Promise<void> => {
    // Wrap the apiFetch call for logging
    return logExecution(`Delete thread ${threadId}`, () =>
        apiFetch<void>(`${BASE_URL}/threads/${threadId}`, {
            method: 'DELETE',
        })
        // Note: No need for .then() log here, logExecution handles failure logging.
    );
};


// --- Authentication API Functions ---

/** Fetches the current user's info from the backend. Returns UserInfo or null if not authenticated. */
export const fetchCurrentUser = async (signal?: AbortSignal): Promise<UserInfo | null> => {
    // Don't wrap this in logExecution by default, as 401 is expected
    // Also, don't clear globalError here, let the caller decide.
    try {
        const userInfo = await apiFetch<UserInfo>(`${BASE_URL}/users/me`, {}, signal);
        return userInfo;
    } catch (error: unknown) {
        // Specifically check for 401 Unauthorized - this means user is not logged in, which is not a "global" error.
        if (error instanceof Error && error.message.includes('Status: 401')) {
            console.log("User not authenticated (401 received from /users/me).");
            return null; // Expected case for logged-out user
        }
        // For other errors (network, 500, etc.), log it and re-throw
        console.error('API Error fetching current user:', error);
        // Optionally set globalError here if desired for non-401 errors during auth check
        // globalError.set(error instanceof Error ? error.message : 'Failed to check login status.');
        throw error; // Re-throw other errors
    }
};

/** Logs the user out by calling the backend endpoint. */
export const logoutUser = (): Promise<{ message: string }> => {
    // Wrap in logExecution for consistent logging/error handling
    return logExecution("Logout user", () =>
        apiFetch<{ message: string }>(`${BASE_URL}/auth/logout`, {
            method: 'POST',
            // No body needed
        })
    );
};

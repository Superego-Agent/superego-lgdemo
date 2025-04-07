// src/lib/api.ts
import { messages, isLoading, globalError, activeConversationId, activeThreadId, activeConstitutionIds, availableConstitutions } from './stores'; // Updated store imports
import { updateConversation } from './conversationManager'; // Import update function
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { nanoid } from 'nanoid';

// Assuming types are defined in global.d.ts or similar and updated:
// type ConstitutionItem = { id: string; title: string; description?: string }; // Updated name -> title
// type MessageType = HumanMessage | AIMessage | ToolResultMessage | SystemMessage; // etc.
// type HistoryResponse = { messages: MessageType[]; thread_id: string; thread_name?: string }; // thread_id is now string
// type StreamRunRequest = { thread_id: string | null; input: any; constitution_ids: string[]; adherence_levels_text?: string }; // Added adherence_levels_text
// type CompareRunRequest = { thread_id: string | null; input: any; constitution_sets: { id: string; constitution_ids: string[] }[] }; // thread_id is string | null
// type SSEEventData = { type: string; data: any; node?: string; set_id?: string };
// type SSEEndData = { thread_id: string }; // thread_id is now string
// type SSEToolCallChunkData = { id?: string; name?: string; args?: string };
// type SSEToolResultData = { result: string; tool_name: string; is_error: boolean; tool_call_id?: string };
// type HumanMessage = { id: string; sender: 'human'; content: string; timestamp: number };
// type AIMessage = { id: string; sender: 'ai'; content: string; node?: string; set_id?: string; timestamp: number; tool_calls?: ToolCall[] };
// type ToolResultMessage = { id: string; sender: 'tool_result'; content: string; tool_name: string; is_error: boolean; node?: string; set_id?: string; timestamp: number; tool_call_id?: string };
// type SystemMessage = { id: string; sender: 'system'; content: string; node?: string; set_id?: string; isError?: boolean; timestamp: number };
// type ToolCall = { id: string; name: string; args: string };
// type CompareSet = { id: string; constitution_ids: string[] }; // Assuming definition

// Ensure this matches your environment (Vite default or custom)
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Helper for standard Fetch requests ---
async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
    const isStreamRequest = options.headers && (options.headers as Record<string, string>)['Accept'] === 'text/event-stream';
    let requestStartedLoading = false;

    // Only set global loading for non-stream requests
    if (!isStreamRequest) {
        isLoading.set(true);
        requestStartedLoading = true; // Mark that this specific request set the loading state
    }
    globalError.set(null);

    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json', // Default, override for streams
                ...options.headers,
            },
        });
        if (!response.ok) {
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try {
                const errorBody = await response.json();
                errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
            } catch (e) { /* Ignore if error body isn't JSON */ }
            throw new Error(errorMsg);
        }
        // isLoading is handled in finally block for non-streams
        // Handle cases where response might be empty (e.g., successful PUT/DELETE with 204 No Content)
        if (response.status === 204) {
            return undefined as T; // Or handle as appropriate for your expected types
        }
        return await response.json() as T;
    } catch (error: any) {
        console.error('API Fetch Error:', url, error);
        globalError.set(error.message || 'An unknown API error occurred.');
        // isLoading is handled in finally block
        throw error; // Re-throw after handling state
    } finally {
        // Only turn off loading if this specific non-stream request turned it on
        if (requestStartedLoading) {
            console.log(`apiFetch finally: Resetting isLoading for ${url}`); // Add log
            isLoading.set(false);
        }
        // Streaming requests manage their own isLoading state via fetchEventSource callbacks (onclose, onerror)
    }
}


// --- API Functions ---

// fetchConstitutions remains the same
export const fetchConstitutions = async (): Promise<ConstitutionItem[]> => {
    console.log('API: Fetching constitutions');
    const constitutions = await apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`);
    // availableConstitutions store needs to be imported if still used directly, otherwise remove .set()
    // Assuming availableConstitutions is still needed and imported:
    // import { availableConstitutions } from './stores'; // Add this import if needed - Already added above
    availableConstitutions.set(constitutions); // Uncommented this line
    return constitutions;
};

// fetchThreads removed - managed by conversationManager now

export const fetchHistory = async (threadId: string): Promise<HistoryResponse> => { // threadId is now string
    console.log(`API: Fetching history for Thread ID ${threadId}`);
    // Assuming HistoryResponse type is updated (thread_id: string)
    try {
        // Use string threadId in URL
        const historyData = await apiFetch<HistoryResponse>(`${BASE_URL}/threads/${threadId}/history`);

        // --- History Transformation REMOVED ---
        // The backend now provides structured tool_calls, so no frontend transformation is needed.

        messages.set(historyData.messages || []); // Set store directly with backend data
        // currentThreadId.set(threadId); // REMOVED - activeThreadId is derived reactively
        // Optionally use historyData.thread_name if needed
        return historyData; // Return original backend data
    } catch (error) {
        console.error(`Failed to fetch history for Thread ID ${threadId}:`, error);
        messages.set([]); // Clear messages on error
        throw error; // Re-throw error after setting state
    }
};


// renameThread removed - handled client-side by conversationManager

interface ConstitutionSubmission {
    text: string;
    is_private: boolean;
}

interface SubmissionResponse {
    status: string;
    message: string;
    email_sent: boolean;
}

export const submitConstitution = async (submission: ConstitutionSubmission): Promise<SubmissionResponse> => {
    console.log('API: Submitting constitution');
    return await apiFetch<SubmissionResponse>(`${BASE_URL}/constitutions/submit`, {
        method: 'POST',
        body: JSON.stringify(submission),
    });
};

// --- Real Streaming Functions ---
let streamController: AbortController | null = null;
export const cancelStream = () => {
    if (streamController) {
        console.log('API: Aborting active stream.');
        streamController.abort();
        streamController = null;
        if (get(isLoading)) {
            isLoading.set(false);
        }
    }
};

// --- SSE Message Handler ---
let lastProcessedNodeId: string | null = null;
// Helper remains the same
function findLastMatchingAiMessageIndex(msgs: MessageType[], nodeId: string | null, setId: string | null): number {
    for (let i = msgs.length - 1; i >= 0; i--) {
        const msg = msgs[i];
        if (msg.sender === 'ai' && (msg.node ?? null) === nodeId) {
            if (!setId || (msg.set_id ?? null) === setId) {
                return i;
            }
        }
    }
    return -1;
}

function handleSSEMessage(event: EventSourceMessage, wasNewThread: boolean) {
    // Added wasNewThread flag
    try {
        if (!event.data) {
            console.warn('SSE message received with no data.');
            return;
        }
        // Assuming SSEEventData and sub-types in global.d.ts are aligned with backend
        const parsedData: SSEEventData = JSON.parse(event.data);
        const setId = parsedData.set_id;
        const currentNodeId = parsedData.node ?? 'graph';

        messages.update(currentMsgs => {
            let updatedMsgs = [...currentMsgs];
            const lastMsgIndex = updatedMsgs.length - 1;
            const lastMessage = lastMsgIndex >= 0 ? updatedMsgs[lastMsgIndex] : null;

            switch (parsedData.type) {
                // Cases 'chunk', 'ai_tool_chunk', 'tool_result', 'error' remain the same logic as before
                case 'chunk':
                    const chunkContent = parsedData.data as string;
                    if (chunkContent === null || chunkContent === undefined) break;
                    if (lastMessage?.sender === 'ai' && lastMessage.node === currentNodeId && lastProcessedNodeId === currentNodeId) {
                        // Append chunk to existing AI message if conditions match
                        updatedMsgs[lastMsgIndex] = { ...lastMessage, content: (lastMessage.content || '') + chunkContent };
                    } else {
                        // Create new AI message
                        const newMsg: AIMessage = {
                            id: nanoid(8), sender: 'ai', content: chunkContent, node: currentNodeId,
                            set_id: setId ?? null, timestamp: Date.now(), tool_calls: [] // Coalesce setId to null
                        };
                        updatedMsgs.push(newMsg);
                    }
                    lastProcessedNodeId = currentNodeId;
                    break;
                case 'ai_tool_chunk':
                    const toolChunkData = parsedData.data as SSEToolCallChunkData;
                    // Ensure setId passed is string | null, not undefined
                    const targetAiMsgIndexTool = findLastMatchingAiMessageIndex(updatedMsgs, currentNodeId, setId ?? null);
                    if (targetAiMsgIndexTool > -1) {
                        let targetMsg = updatedMsgs[targetAiMsgIndexTool] as AIMessage;
                        if (!targetMsg.tool_calls) { targetMsg.tool_calls = []; }
                        let existingCallIndex = -1;
                        if (toolChunkData.id) {
                             existingCallIndex = targetMsg.tool_calls.findIndex(tc => tc.id === toolChunkData.id);
                        } else {
                             existingCallIndex = targetMsg.tool_calls.length > 0 ? targetMsg.tool_calls.length - 1 : -1;
                             if (existingCallIndex !== -1) console.warn("Tool chunk missing ID, applying to last tool call.");
                        }
                        if (existingCallIndex !== -1) {
                            targetMsg.tool_calls[existingCallIndex] = {
                                ...targetMsg.tool_calls[existingCallIndex],
                                name: toolChunkData.name ?? targetMsg.tool_calls[existingCallIndex].name,
                                args: (targetMsg.tool_calls[existingCallIndex].args || "") + (toolChunkData.args || ""),
                            };
                        } else if (toolChunkData.name) {
                            targetMsg.tool_calls.push({
                                id: toolChunkData.id || nanoid(6),
                                name: toolChunkData.name,
                                args: toolChunkData.args || "",
                            });
                        } else {
                             console.warn("Received ai_tool_chunk with no name or matching ID.", toolChunkData);
                        }
                        updatedMsgs[targetAiMsgIndexTool] = { ...targetMsg };
                    } else { console.warn("Received ai_tool_chunk but no matching AI message found.", parsedData); }
                    lastProcessedNodeId = currentNodeId;
                    break;
                case 'tool_result':
                    const toolResultData = parsedData.data as SSEToolResultData;
                    const newToolResultMsg: ToolResultMessage = {
                        id: nanoid(8), sender: 'tool_result', content: toolResultData.result,
                        tool_name: toolResultData.tool_name, is_error: toolResultData.is_error,
                        node: currentNodeId, set_id: setId ?? null, timestamp: Date.now(), // Coalesce setId to null
                        tool_call_id: toolResultData.tool_call_id
                    };
                    updatedMsgs.push(newToolResultMsg);
                    lastProcessedNodeId = currentNodeId;
                    break;
                case 'error':
                    const errorMsg = parsedData.data as string;
                    console.error(`SSE Error Event (node: ${currentNodeId}, set: ${setId || 'N/A'}):`, errorMsg);
                    const newErrorMsg: SystemMessage = {
                        id: nanoid(8), sender: 'system',
                        content: `Error (node: ${currentNodeId || 'graph'}, set: ${setId || 'general'}): ${errorMsg}`,
                        node: currentNodeId, set_id: setId ?? null, isError: true, timestamp: Date.now() // Coalesce setId to null
                    };
                    updatedMsgs.push(newErrorMsg);
                    lastProcessedNodeId = 'error_node';
                    break;

                case 'end':
                    // --- UPDATED HANDLING for 'end' ---
                    const endData = parsedData.data as SSEEndData; // Assuming SSEEndData has thread_id: string
                    const endedThreadId = endData?.thread_id; // Now a string UUID
                    console.log(`SSE Stream ended (node: ${currentNodeId}, set: ${setId || 'N/A'}, Backend Thread ID: ${endedThreadId})`);

                    if (wasNewThread && typeof endedThreadId === 'string' && endedThreadId) {
                        const currentConversationId = get(activeConversationId); // Get client-side ID (string | null)
                        const currentActiveConstitutions = get(activeConstitutionIds); // Get constitutions used (string[])

                        if (currentConversationId) {
                            // Explicitly type the const to help TS within the block
                            const convId: string = currentConversationId;
                            console.log(`Updating localStorage conversation ${convId} with backend thread_id ${endedThreadId} and constitutions [${currentActiveConstitutions.join(', ')}]`);
                            // Call updateConversation with the explicitly typed string ID
                            updateConversation(convId, {
                                thread_id: endedThreadId, // endedThreadId is confirmed string here
                                last_used_constitution_ids: currentActiveConstitutions
                            });
                            // Explicitly update activeThreadId store as the subscription might not catch the localStorage change
                            if (get(activeConversationId) === convId) { // Check if the conversation is still active
                                console.log(`api.ts end event: Explicitly setting activeThreadId to ${endedThreadId}`);
                                activeThreadId.set(endedThreadId);
                            }
                        } else {
                            console.error("SSE 'end' event received for new thread, but no activeConversationId was set in the store!");
                        }
                        // fetchThreads(); // REMOVED
                    } else if (wasNewThread) {
                         console.error("SSE 'end' event received for new thread, but no valid thread_id string was provided in the payload:", endData);
                    }
                    lastProcessedNodeId = null; // Reset node tracker
                    break;
                    // --- END UPDATED HANDLING ---

                default:
                    console.warn('Unhandled SSE event type:', parsedData.type);
            }
            return updatedMsgs;
        });
    } catch (error) {
        console.error('Failed to parse SSE message data:', event.data, error);
        globalError.set(`Received malformed message from server: ${error instanceof Error ? error.message : String(error)}`);
        lastProcessedNodeId = null;
    }
}


// --- Core Streaming Function (Common Logic) ---
async function performStreamRequest(
    endpoint: string,
    requestBody: StreamRunRequest | CompareRunRequest,
    wasNewThread: boolean // Flag to indicate if this request is creating a new thread
): Promise<void> {
    console.log(`API: Connecting to ${BASE_URL}${endpoint}`);
    isLoading.set(true);
    globalError.set(null);
    cancelStream(); // Cancel existing stream

    lastProcessedNodeId = null; // Reset node tracker

    const controller = new AbortController();
    streamController = controller;

    try {
        await fetchEventSource(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify(requestBody),
            signal: controller.signal,
            openWhenHidden: true,

            onopen: async (response) => {
                if (!response.ok) {
                    let errorMsg = `SSE connection failed! Status: ${response.status}`;
                    try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ }
                    if (streamController === controller) { isLoading.set(false); streamController = null; lastProcessedNodeId = null; }
                    throw new Error(errorMsg);
                }
                console.log(`SSE stream opened (${endpoint})`);
            },
            onmessage: (event) => {
                // Pass wasNewThread flag to handler
                handleSSEMessage(event, wasNewThread);
            },
            onclose: () => {
                console.log(`SSE stream closed (${endpoint}).`);
                if (streamController === controller) {
                    isLoading.set(false);
                    streamController = null;
                    lastProcessedNodeId = null;
                    // No longer need to refresh threads here, moved to 'end' event handling
                }
            },
            onerror: (err) => {
                if (controller.signal.aborted) {
                    console.log("Stream intentionally aborted.");
                     if (streamController === controller) { isLoading.set(false); streamController = null; lastProcessedNodeId = null;}
                    return; // Stop further processing
                }
                console.error(`SSE stream error (${endpoint}):`, err);
                if (streamController === controller) {
                    isLoading.set(false);
                    globalError.set(`Stream connection error: ${err.message || 'Unknown stream error'}`);
                    streamController = null;
                    lastProcessedNodeId = null;
                }
                throw err; // Rethrow
            },
        });
    } catch (error) {
        // Catch errors from setup/connection
        if (!controller.signal.aborted) {
            console.error(`Stream setup (${endpoint}) failed:`, error);
             if (streamController === controller) {
                 if (get(isLoading)) { isLoading.set(false); }
                 if (!get(globalError)) { globalError.set(`Stream setup failed: ${error instanceof Error ? error.message : String(error)}`); }
                 streamController = null;
                 lastProcessedNodeId = null;
             }
        } else {
             console.log("Stream aborted during setup phase.");
             if (streamController === controller) {
                if (get(isLoading)) { isLoading.set(false); }
                 streamController = null;
                 lastProcessedNodeId = null;
             }
        }
    }
}

// --- Specific Stream Run Functions ---
export const streamRun = async (
    userInput: string,
    threadId: string | null, // Now string | null (UUID)
    constitutionIds: string[] = [], // Default to empty list, backend handles 'none' if empty
    adherenceLevelsText?: string // Optional adherence text
): Promise<void> => {
    // Ensure StreamRunRequest type definition includes adherence_levels_text
    const requestBody: StreamRunRequest = {
        thread_id: threadId,
        input: { type: 'human', content: userInput },
        // Send empty list if no constitutions selected, backend defaults to 'none'
        constitution_ids: constitutionIds.length > 0 ? constitutionIds : ['none'],
        adherence_levels_text: adherenceLevelsText || undefined // Add adherence text if provided
    };
    const wasNewThread = threadId === null; // Determine if this is for a new thread
    if (wasNewThread) {
         console.log("API: streamRun initiating new thread.");
         // Clear messages immediately for a new chat feel
         messages.set([]);
    } else {
         console.log(`API: streamRun continuing thread ${threadId}.`);
    }
    await performStreamRequest('/runs/stream', requestBody, wasNewThread);
};

export const fetchConstitutionContent = async (constitutionId: string): Promise<string> => {
    console.log(`API: Fetching content for constitution ${constitutionId}`);
    const url = `${BASE_URL}/constitutions/${constitutionId}/content`;
    // We expect plain text, so use fetch directly, not apiFetch helper which expects JSON
    try {
        const response = await fetch(url, {
            headers: {
                'Accept': 'text/plain', // Request plain text
            },
        });
        if (!response.ok) {
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try {
                // Try to get text detail even for non-JSON error
                const errorText = await response.text();
                errorMsg += ` - ${errorText}`;
            } catch (e) { /* Ignore */ }
            throw new Error(errorMsg);
        }
        return await response.text();
    } catch (error: any) {
        console.error(`API Fetch Error (Content): ${url}`, error);
        globalError.set(error.message || `Failed to load content for ${constitutionId}.`);
        throw error; // Re-throw
    }
    // No isLoading handling here as it's a quick fetch, managed by the calling component
};


// streamCompareRun needs similar adjustments if used
export const streamCompareRun = async (
    userInput: string,
    threadId: string | null, // Now string | null (UUID)
    compareSetsConfig: CompareSet[] // Assuming CompareSet type is defined
): Promise<void> => {
     // TODO: Ensure CompareRunRequest type definition (e.g., in global.d.ts)
     // is updated to expect thread_id: string | null
    const requestBody: CompareRunRequest = {
        thread_id: threadId, // Pass string UUID or null (TS error here implies type def needs update)
        input: { type: 'human', content: userInput },
        constitution_sets: compareSetsConfig.map(set => ({ id: set.id, constitution_ids: set.constitution_ids }))
    };
     const wasNewThread = threadId === null; // Determine if this is for a new thread
     if (wasNewThread) {
         console.log("API: streamCompareRun initiating new thread.");
         messages.set([]); // Clear messages for new compare view
     } else {
         console.log(`API: streamCompareRun continuing thread ${threadId}.`);
         // Decide if you want to clear messages when running compare on an existing thread
         // messages.set([]); // Uncomment to clear messages for compare run on existing thread
     }
    await performStreamRequest('/runs/compare/stream', requestBody, wasNewThread);
};

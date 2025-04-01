// src/lib/api.ts
import { messages, isLoading, globalError, currentThreadId, availableThreads, availableConstitutions } from './stores';
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { nanoid } from 'nanoid';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Helper for standard Fetch requests ---
async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
    isLoading.set(true);
    globalError.set(null);
    try {
        const response = await fetch(url, {
            ...options,
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
        // Don't set isLoading false here for streams
        if (!options.signal && !(options.headers && (options.headers as Record<string, string>)['Accept'] === 'text/event-stream')) {
            isLoading.set(false);
        }
        return await response.json() as T;
    } catch (error: any) {
        console.error('API Fetch Error:', error);
        globalError.set(error.message || 'An unknown API error occurred.');
         // Don't set isLoading false here for streams
        if (!options.signal && !(options.headers && (options.headers as Record<string, string>)['Accept'] === 'text/event-stream')) {
            isLoading.set(false);
        }
        throw error;
    }
}

// --- API Functions ---
export const fetchConstitutions = async (): Promise<ConstitutionItem[]> => {
    console.log('API: Fetching constitutions');
    const constitutions = await apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`);
    availableConstitutions.set(constitutions);
    return constitutions;
};

export const fetchThreads = async (): Promise<ThreadItem[]> => {
    console.log('API: Fetching threads');
    const threads = await apiFetch<ThreadItem[]>(`${BASE_URL}/threads`);
    availableThreads.set(threads);
    return threads;
};

export const fetchHistory = async (threadId: string): Promise<HistoryResponse> => {
    console.log(`API: Fetching history for ${threadId}`);
    try {
        const history = await apiFetch<HistoryResponse>(`${BASE_URL}/threads/${threadId}/history`);
        messages.set(history.messages || []);
        return history;
    } catch (error) {
        console.error(`Failed to fetch history for ${threadId}:`, error);
        messages.set([]);
        throw error;
    }
};

export const createNewThread = async (): Promise<NewThreadResponse> => {
    console.log('API: Creating new thread');
    const newThread = await apiFetch<NewThreadResponse>(`${BASE_URL}/threads`, { method: 'POST' });
    currentThreadId.set(newThread.thread_id);
    messages.set([]); // Clear messages for new thread
    fetchThreads(); // Refresh thread list
    return newThread;
};

// --- Real Streaming Functions ---
let streamController: AbortController | null = null;
export const cancelStream = () => {
    if (streamController) {
        console.log('API: Aborting active stream.');
        streamController.abort();
        streamController = null;
        // Ensure loading state is reset if we abort
        if (get(isLoading)) {
            isLoading.set(false);
        }
    }
};

// --- SSE Message Handler (Simplified Node Change Logic, Original Tool Chunk Handling) ---

// Variable to track the last node processed *during the current stream*
let lastProcessedNodeId: string | null = null;

// Helper to find the last AI message matching node/set (needed for original tool chunk logic)
// Note: This is slightly different from the original `findLastAiMessageIndex` as it now only needs the index
function findLastMatchingAiMessageIndex(msgs: MessageType[], nodeId: string | null, setId: string | null): number {
    // Search backwards for the last AI message that matches the node and set criteria
    for (let i = msgs.length - 1; i >= 0; i--) {
        const msg = msgs[i];
        if (msg.sender === 'ai' && (msg.node ?? null) === nodeId) {
            // If setId is provided, it must match; otherwise, ignore setId matching
            if (!setId || (msg.set_id ?? null) === setId) {
                return i;
            }
        }
    }
    return -1; // Not found
}


function handleSSEMessage(event: EventSourceMessage) {
    try {
        if (!event.data) {
            console.warn('SSE message received with no data.');
            return;
        }
        const parsedData: SSEEventData = JSON.parse(event.data);
        const setId = parsedData.set_id;
        const currentNodeId = parsedData.node ?? 'graph'; // Default if node is missing

        messages.update(currentMsgs => {
            let updatedMsgs = [...currentMsgs];
            const lastMsgIndex = updatedMsgs.length - 1;
            const lastMessage = lastMsgIndex >= 0 ? updatedMsgs[lastMsgIndex] : null;

            switch (parsedData.type) {
                case 'chunk':
                    const chunkContent = parsedData.data as string;
                    if (chunkContent === null || chunkContent === undefined) break;

                    // Append to last message if it's an AI message from the same node, otherwise create new
                    if (lastMessage?.sender === 'ai' && lastMessage.node === currentNodeId && lastProcessedNodeId === currentNodeId) {
                        updatedMsgs[lastMsgIndex] = {
                            ...lastMessage,
                            content: (lastMessage.content || '') + chunkContent
                        };
                    } else {
                        // Create new AI message bubble
                        const newMsg: AIMessage = {
                            id: nanoid(8),
                            sender: 'ai',
                            content: chunkContent,
                            node: currentNodeId,
                            set_id: setId,
                            timestamp: Date.now(),
                            tool_calls: []
                        };
                        updatedMsgs.push(newMsg);
                    }
                    lastProcessedNodeId = currentNodeId;
                    break;

                case 'ai_tool_chunk':
                    // *** RESTORED ORIGINAL LOGIC FOR TOOL CHUNKS ***
                    const toolChunkData = parsedData.data as SSEToolCallChunkData;
                    const targetAiMsgIndexTool = findLastMatchingAiMessageIndex(updatedMsgs, currentNodeId, setId); // Use helper to find correct message

                    if (targetAiMsgIndexTool > -1) {
                        let targetMsg = updatedMsgs[targetAiMsgIndexTool] as AIMessage;
                        if (!targetMsg.tool_calls) { targetMsg.tool_calls = []; } // Ensure array exists

                        // Original logic: Find tool call by ID or assume sequential if ID missing
                        let existingCallIndex = -1;
                        if (toolChunkData.id) {
                             existingCallIndex = targetMsg.tool_calls.findIndex(tc => tc.id === toolChunkData.id);
                        } else {
                             // Fallback: assume it applies to the last tool call if ID is missing (less robust)
                             existingCallIndex = targetMsg.tool_calls.length > 0 ? targetMsg.tool_calls.length - 1 : -1;
                             if (existingCallIndex !== -1) console.warn("Tool chunk missing ID, applying to last tool call.");
                        }


                        if (existingCallIndex !== -1) {
                            // Update existing tool call
                            targetMsg.tool_calls[existingCallIndex] = {
                                ...targetMsg.tool_calls[existingCallIndex], // Keep existing data
                                name: toolChunkData.name ?? targetMsg.tool_calls[existingCallIndex].name, // Update name if provided
                                args: (targetMsg.tool_calls[existingCallIndex].args || "") + (toolChunkData.args || ""), // Append args
                            };
                        } else if (toolChunkData.name) {
                            // If it's a new tool call (has name, but wasn't found by ID)
                            targetMsg.tool_calls.push({
                                id: toolChunkData.id || nanoid(6), // Use ID if provided, else generate temp one
                                name: toolChunkData.name,
                                args: toolChunkData.args || "", // Start args string
                            });
                        } else {
                             // Chunk has neither name nor matching ID. Ignore/Warn.
                             console.warn("Received ai_tool_chunk with no name or matching ID.", toolChunkData);
                        }
                        // Ensure reactivity for the message object
                        updatedMsgs[targetAiMsgIndexTool] = { ...targetMsg };

                    } else { console.warn("Received ai_tool_chunk but no matching AI message found.", parsedData); }
                     // *** END OF RESTORED LOGIC ***
                    lastProcessedNodeId = currentNodeId; // Mark AI node as last active
                    break;

                case 'tool_result':
                    const toolResultData = parsedData.data as SSEToolResultData;
                    // Always create a new bubble for tool results
                    const newToolResultMsg: ToolResultMessage = {
                        id: nanoid(8),
                        sender: 'tool_result',
                        content: toolResultData.result,
                        tool_name: toolResultData.tool_name,
                        is_error: toolResultData.is_error,
                        node: currentNodeId, // Node here is typically 'tools'
                        set_id: setId,
                        timestamp: Date.now(),
                        tool_call_id: toolResultData.tool_call_id
                    };
                    updatedMsgs.push(newToolResultMsg);
                    lastProcessedNodeId = currentNodeId; // Mark that 'tools' node was last active
                    break;

                case 'error':
                    const errorMsg = parsedData.data as string;
                    console.error(`SSE Error Event (node: ${currentNodeId}, set: ${setId || 'N/A'}):`, errorMsg);
                    // Always create a new bubble for errors
                    const newErrorMsg: SystemMessage = {
                        id: nanoid(8),
                        sender: 'system',
                        content: `Error (node: ${currentNodeId || 'graph'}, set: ${setId || 'general'}): ${errorMsg}`,
                        node: currentNodeId,
                        set_id: setId,
                        isError: true,
                        timestamp: Date.now()
                    };
                    updatedMsgs.push(newErrorMsg);
                    lastProcessedNodeId = 'error_node'; // Indicate error occurred
                    break;

                case 'end':
                    const endData = parsedData.data as SSEEndData;
                    console.log(`SSE Stream ended (node: ${currentNodeId}, set: ${setId || 'N/A'}, thread: ${endData?.thread_id})`);
                    // Reset last node tracker when the stream for this request ends
                    lastProcessedNodeId = null;
                    break;

                default:
                    console.warn('Unhandled SSE event type:', parsedData.type);
            }
            return updatedMsgs; // Return the modified message array
        });
    } catch (error) {
        console.error('Failed to parse SSE message data:', event.data, error);
        globalError.set(`Received malformed message from server: ${error instanceof Error ? error.message : String(error)}`);
        // Attempt to reset node tracker in case of parse error
        lastProcessedNodeId = null;
    }
}

// --- Core Streaming Function (Common Logic) ---
// (No changes needed in performStreamRequest, streamRun, streamCompareRun from the previous version)
async function performStreamRequest( endpoint: string, requestBody: StreamRunRequest | CompareRunRequest ): Promise<void> {
    console.log(`API: Connecting to ${endpoint}`);
    isLoading.set(true);
    globalError.set(null);
    // Cancel any existing stream before starting a new one
    cancelStream();

    // Reset last processed node for the new stream
    lastProcessedNodeId = null;

    const controller = new AbortController();
    streamController = controller; // Store the controller to allow cancellation

    try {
        await fetchEventSource(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify(requestBody),
            signal: controller.signal,
            openWhenHidden: true, // Keep connection alive even if tab is backgrounded

            onopen: async (response) => {
                if (!response.ok) {
                    // Handle non-2xx responses before starting stream
                    let errorMsg = `SSE connection failed! Status: ${response.status}`;
                    try {
                        const errorBody = await response.json();
                        errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
                    } catch (e) { /* Ignore if error body isn't JSON */ }
                    isLoading.set(false);
                    streamController = null; // Clear controller on failure
                    lastProcessedNodeId = null;
                    throw new Error(errorMsg); // Throw to be caught by outer catch
                }
                console.log(`SSE stream opened (${endpoint})`);
                // Stream is open, loading is handled by onclose/onerror
            },
            onmessage: (event) => {
                // Process messages using our handler
                handleSSEMessage(event);
            },
            onclose: () => {
                console.log(`SSE stream closed (${endpoint}).`);
                // Only reset loading/controller if this is the active controller closing
                if (streamController === controller) {
                    isLoading.set(false);
                    streamController = null;
                    lastProcessedNodeId = null; // Reset tracker
                }
                 // After a stream for a *new* thread finishes successfully, refresh thread list
                 const reqBody = requestBody as StreamRunRequest; // Assume StreamRunRequest structure for this check
                 if (endpoint === '/runs/stream' && reqBody.input && reqBody.thread_id === null && !controller.signal.aborted) {
                     console.log("New thread stream finished, refreshing threads list.");
                     fetchThreads(); // Fetch updated thread list
                 }
            },
            onerror: (err) => {
                // Don't throw an error if the stream was intentionally aborted
                if (controller.signal.aborted) {
                    console.log("Stream intentionally aborted.");
                     if (streamController === controller) { // Ensure cleanup if aborted
                        isLoading.set(false);
                        streamController = null;
                        lastProcessedNodeId = null;
                    }
                    return; // Stop further processing for aborted streams
                }
                console.error(`SSE stream error (${endpoint}):`, err);
                if (streamController === controller) { // Only update state if it's the active stream failing
                    isLoading.set(false);
                    globalError.set(`Stream connection error: ${err.message || 'Unknown stream error'}`);
                    streamController = null;
                    lastProcessedNodeId = null; // Reset tracker
                }
                // Rethrow the error AFTER setting loading/error state,
                // so the fetchEventSource internals know an error occurred.
                throw err;
            },
        });
    } catch (error) {
        // Catch errors from fetchEventSource setup (e.g., network issues, onopen non-2xx throw)
        // Check if it was aborted - aborts can sometimes manifest as exceptions depending on timing
        if (!controller.signal.aborted) {
            console.error(`Stream setup (${endpoint}) failed:`, error);
             // Ensure state is reset if setup fails and it's the current controller
             if (streamController === controller) {
                 if (get(isLoading)) { isLoading.set(false); }
                 if (!get(globalError)) { globalError.set(`Stream setup failed: ${error instanceof Error ? error.message : String(error)}`); }
                 streamController = null;
                 lastProcessedNodeId = null;
             }
        } else {
            console.log("Stream intentionally aborted (caught exception during setup/early phase).");
            // Ensure state is reset if aborted during setup
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
    threadId: string | null,
    constitutionIds: string[] = ['none']
): Promise<void> => {
    const requestBody: StreamRunRequest = {
        thread_id: threadId,
        input: { type: 'human', content: userInput },
        constitution_ids: constitutionIds
    };
    await performStreamRequest('/runs/stream', requestBody);
};

export const streamCompareRun = async (
    userInput: string,
    compareSetsConfig: CompareSet[]
): Promise<void> => {
    const requestBody: CompareRunRequest = {
        input: { type: 'human', content: userInput },
        constitution_sets: compareSetsConfig.map(set => ({ id: set.id, constitution_ids: set.constitution_ids })) // Ensure format matches backend
    };
    await performStreamRequest('/runs/compare/stream', requestBody);
};
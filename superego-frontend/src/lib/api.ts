// src/lib/api.ts
import { messages, isLoading, globalError, currentThreadId, availableThreads, availableConstitutions, resetForNewChat } from './stores';
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { nanoid } from 'nanoid';

// Ensure this matches your environment (Vite default or custom)
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Helper for standard Fetch requests ---
async function apiFetch<T>(url: string, options: RequestInit = {}): Promise<T> {
    isLoading.set(true);
    globalError.set(null);
    let isStream = options.headers && (options.headers as Record<string, string>)['Accept'] === 'text/event-stream';

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
        // Don't set isLoading false here for event streams initiated via this helper (though usually not)
        if (!isStream && !options.signal) {
             isLoading.set(false);
        }
        // Handle cases where response might be empty (e.g., successful PUT/DELETE with 204 No Content)
        if (response.status === 204) {
            return undefined as T; // Or handle as appropriate for your expected types
        }
        return await response.json() as T;
    } catch (error: any) {
        console.error('API Fetch Error:', url, error);
        globalError.set(error.message || 'An unknown API error occurred.');
        // Don't set isLoading false here for streams
         if (!isStream && !options.signal) {
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
    // Assuming ThreadItem in global.d.ts now has id: number, last_updated?: string | Date
    const threads = await apiFetch<ThreadItem[]>(`${BASE_URL}/threads`);
    availableThreads.set(threads);
    return threads;
};

export const fetchHistory = async (threadId: number): Promise<HistoryResponse> => {
    console.log(`API: Fetching history for Thread ID ${threadId}`);
    // Assuming HistoryResponse in global.d.ts now has thread_id: number, thread_name?: string
    try {
        const historyData = await apiFetch<HistoryResponse>(`${BASE_URL}/threads/${threadId}/history`);
        messages.set(historyData.messages || []);
        currentThreadId.set(threadId); // Set the active thread ID
        // Optionally store/display historyData.thread_name in the UI
        return historyData;
    } catch (error) {
        console.error(`Failed to fetch history for Thread ID ${threadId}:`, error);
        // Don't reset currentThreadId here, maybe the thread exists but history fetch failed
        messages.set([]);
        throw error;
    }
};

// Removed createNewThread - handled implicitly by streamRun/streamCompareRun

export const renameThread = async (threadId: number, newName: string): Promise<ThreadItem | void> => {
    console.log(`API: Renaming Thread ID ${threadId} to "${newName}"`);
    try {
        // Assuming backend returns the updated ThreadItem on success or 204/error
        const updatedThread = await apiFetch<ThreadItem>(`${BASE_URL}/threads/${threadId}/rename`, {
            method: 'PUT',
            body: JSON.stringify({ new_name: newName }),
        });
        await fetchThreads(); // Refresh the threads list in the store
        return updatedThread;
    } catch (error) {
        console.error(`Failed to rename Thread ID ${threadId}:`, error);
        // Error is already set by apiFetch
        throw error;
    }
};

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
                        updatedMsgs[lastMsgIndex] = { ...lastMessage, content: (lastMessage.content || '') + chunkContent };
                    } else {
                        const newMsg: AIMessage = {
                            id: nanoid(8), sender: 'ai', content: chunkContent, node: currentNodeId,
                            set_id: setId, timestamp: Date.now(), tool_calls: []
                        };
                        updatedMsgs.push(newMsg);
                    }
                    lastProcessedNodeId = currentNodeId;
                    break;
                case 'ai_tool_chunk':
                    const toolChunkData = parsedData.data as SSEToolCallChunkData;
                    const targetAiMsgIndexTool = findLastMatchingAiMessageIndex(updatedMsgs, currentNodeId, setId);
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
                        node: currentNodeId, set_id: setId, timestamp: Date.now(),
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
                        node: currentNodeId, set_id: setId, isError: true, timestamp: Date.now()
                    };
                    updatedMsgs.push(newErrorMsg);
                    lastProcessedNodeId = 'error_node';
                    break;

                case 'end':
                    // --- UPDATED HANDLING for 'end' ---
                    const endData = parsedData.data as SSEEndData; // Assuming SSEEndData has thread_id: number
                    const endedThreadId = endData?.thread_id;
                    console.log(`SSE Stream ended (node: ${currentNodeId}, set: ${setId || 'N/A'}, Metadata Thread ID: ${endedThreadId})`);

                    if (wasNewThread && typeof endedThreadId === 'number') {
                        console.log(`Updating currentThreadId to newly created ID: ${endedThreadId}`);
                        currentThreadId.set(endedThreadId);
                        // Refresh thread list after a new thread is confirmed created
                        fetchThreads();
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
    threadId: number | null, // Now number | null
    constitutionIds: string[] = ['none']
): Promise<void> => {
    const requestBody: StreamRunRequest = {
        thread_id: threadId, // Pass number or null
        input: { type: 'human', content: userInput },
        constitution_ids: constitutionIds
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

export const streamCompareRun = async (
    userInput: string,
    threadId: number | null, // Now number | null
    compareSetsConfig: CompareSet[]
): Promise<void> => {
    const requestBody: CompareRunRequest = {
        thread_id: threadId, // Pass number or null
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
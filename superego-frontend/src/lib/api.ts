// src/lib/api.ts
import { messages, isLoading, globalError, currentThreadId, availableThreads, availableConstitutions } from './stores';
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';

const BASE_URL = 'http://localhost:8000/api'; // Your backend API base URL

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
			} catch (e) {
				// Ignore if response body is not JSON or empty
			}
			throw new Error(errorMsg);
		}
		return await response.json() as T;
	} catch (error: any) {
		console.error('API Fetch Error:', error);
		globalError.set(error.message || 'An unknown API error occurred.');
		throw error; // Re-throw to allow specific handling if needed
	} finally {
		// isLoading is handled differently for streaming vs non-streaming
		// Set isLoading to false only if it's not a streaming call (handled in stream functions)
		if (!options.signal) { // Simple check: streams usually pass a signal
             // isLoading.set(false); // Handled within calling context or stream handlers now
        }
	}
}


// --- API Functions ---

export const fetchConstitutions = async (): Promise<ConstitutionItem[]> => {
	console.log('API: Fetching constitutions');
    try {
	    const constitutions = await apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`);
        availableConstitutions.set(constitutions); // Update store
        return constitutions;
    } finally {
        isLoading.set(false); // Ensure loading stops for this specific call
    }
};

export const fetchThreads = async (): Promise<ThreadItem[]> => {
	console.log('API: Fetching threads');
    try {
	    const threads = await apiFetch<ThreadItem[]>(`${BASE_URL}/threads`);
        // Assuming API returns sorted or sort here if needed
        availableThreads.set(threads); // Update store
        return threads;
    } finally {
         // isLoading.set(false); // Let Sidebar handle its own loading if needed
    }
};

export const fetchHistory = async (threadId: string): Promise<HistoryResponse> => {
	console.log(`API: Fetching history for ${threadId}`);
    // isLoading is set by apiFetch
    try {
	    const history = await apiFetch<HistoryResponse>(`${BASE_URL}/threads/${threadId}/history`);
        // TODO: Adapt backend HistoryResponse structure to MessageType[] if needed
        // For now, assume it's compatible or requires mapping
        messages.set(history.messages || []); // Update message store
	    return history;
    } finally {
        isLoading.set(false); // Ensure loading stops for this specific call
    }
};

export const createNewThread = async (): Promise<NewThreadResponse> => {
	console.log('API: Creating new thread');
    // isLoading is set by apiFetch
    try {
	    const newThread = await apiFetch<NewThreadResponse>(`${BASE_URL}/threads`, { method: 'POST' });
        currentThreadId.set(newThread.thread_id); // Update current thread ID store
        messages.set([]); // Clear messages for new thread
        // Refresh thread list in the sidebar after creating
        fetchThreads();
	    return newThread;
    } finally {
         isLoading.set(false); // Ensure loading stops for this specific call
    }
};

// --- Real Streaming Functions using fetchEventSource ---

// Shared controller to allow aborting streams
let streamController: AbortController | null = null;

// Function to cancel any ongoing stream
export const cancelStream = () => {
    if (streamController) {
        console.log('API: Aborting active stream.');
        streamController.abort();
        streamController = null;
        isLoading.set(false); // Ensure loading indicator stops
    }
};


// Function to handle incoming SSE messages and update state
function handleSSEMessage(event: EventSourceMessage) {
    try {
        const parsedData: SSEEventData = JSON.parse(event.data);
        const setId = parsedData.set_id; // For compare mode

        // Use a unique ID for each incoming event part for Svelte's keyed each blocks
        const eventPartId = `evt-${event.id || Date.now()}-${Math.random().toString(36).substring(2, 7)}`;

        messages.update(currentMsgs => {
            let updatedMsgs = [...currentMsgs];
            let targetMessageIndex = -1;

            // Find the latest relevant message to update (usually AI or Tool) for this set_id
            if (parsedData.type === 'chunk' || parsedData.type === 'tool_result') {
                 targetMessageIndex = updatedMsgs.findLastIndex(m =>
                    m.sender === (parsedData.type === 'chunk' ? 'ai' : 'tool') &&
                    (setId === undefined || m.set_id === setId) && // Match set_id if present
                    (parsedData.type !== 'tool_result' || (m as ToolCallMessage).tool_name === parsedData.data.tool_name) // Match tool name for results
                 );
            }

            switch (parsedData.type) {
                case 'chunk':
                    const chunkContent = parsedData.data as string;
                    if (targetMessageIndex > -1 && updatedMsgs[targetMessageIndex].sender === 'ai') {
                        // Append chunk to existing AI message
                        updatedMsgs[targetMessageIndex].content += chunkContent;
                        // Update timestamp to keep it fresh for sorting? Maybe not necessary.
                    } else {
                        // Create new AI message if none exists for this stream segment/set_id
                        const newMsg: AIMessage = {
                            id: eventPartId, // Use event ID or generate one
                            sender: 'ai',
                            content: chunkContent,
                            node: parsedData.node,
                            set_id: setId,
                            timestamp: Date.now(),
                        };
                        updatedMsgs.push(newMsg);
                    }
                    break;

                case 'tool_call':
                    const toolCallData = parsedData.data as SSEToolCallData;
                    const newToolCallMsg: ToolCallMessage = {
                        id: eventPartId,
                        sender: 'tool',
                        content: `Calling tool: ${toolCallData.name}...`,
                        tool_name: toolCallData.name,
                        tool_args: toolCallData.args,
                        status: 'started',
                        node: parsedData.node,
                        set_id: setId,
                        timestamp: Date.now(),
                    };
                    updatedMsgs.push(newToolCallMsg);
                    break;

                case 'tool_result':
                    const toolResultData = parsedData.data as SSEToolResultData;
                     if (targetMessageIndex > -1 && updatedMsgs[targetMessageIndex].sender === 'tool') {
                         const targetMsg = updatedMsgs[targetMessageIndex] as ToolCallMessage;
                         targetMsg.status = toolResultData.is_error ? 'error' : 'completed';
                         targetMsg.result = toolResultData.result;
                         targetMsg.is_error = toolResultData.is_error;
                         // Update content to reflect result (optional, MessageCard can handle display)
                         targetMsg.content = `Tool Result: ${toolResultData.tool_name} -> ${toolResultData.result.substring(0, 100)}${toolResultData.result.length > 100 ? '...' : ''}`;
                     } else {
                         // Log warning or potentially create a disconnected tool result message?
                         console.warn("Received tool_result but couldn't find matching tool_call message:", parsedData);
                         // Add a system message indicating the result?
                          updatedMsgs.push({
                             id: eventPartId,
                             sender: 'system',
                             content: `Received result for tool '${toolResultData.tool_name}': ${toolResultData.result}`,
                             node: parsedData.node,
                             set_id: setId,
                             isError: toolResultData.is_error,
                             timestamp: Date.now()
                          });
                     }
                    break;

                case 'error':
                    const errorMsg = parsedData.data as string;
                    console.error(`SSE Error Event (set_id: ${setId || 'N/A'}):`, errorMsg);
                    // Add a system message to the chat
                    updatedMsgs.push({
                        id: eventPartId,
                        sender: 'system',
                        content: `Error (set: ${setId || 'general'}): ${errorMsg}`,
                        node: parsedData.node,
                        set_id: setId,
                        isError: true,
                        timestamp: Date.now(),
                    });
                    // Optionally set globalError as well
                    globalError.set(`Stream Error (set: ${setId || 'general'}): ${errorMsg}`);
                    break;

                case 'end':
                    const endData = parsedData.data as SSEEndData;
                    console.log(`SSE Stream ended for thread ${endData.thread_id} (set_id: ${setId || 'N/A'})`);
                    // If it's a new chat stream that just ended, update the thread list
                    if (!get(currentThreadId) && endData.thread_id) {
                         currentThreadId.set(endData.thread_id);
                         fetchThreads(); // Refresh thread list
                    }
                    // Note: isLoading is handled in the onclose/onerror handlers of fetchEventSource
                    break;

                default:
                    console.warn('Unhandled SSE event type:', parsedData.type);
            }
            return updatedMsgs;
        });

    } catch (error) {
        console.error('Failed to parse SSE message data:', event.data, error);
        globalError.set('Received malformed message from server.');
    }
}


// Stream for 'chat' or 'use' mode
export const streamRun = async (
    userInput: string,
    threadId: string | null,
    constitutionIds: string[] = ['none']
): Promise<void> => {
    console.log(`API: streamRun connecting (thread ${threadId || 'new'}, consts: ${constitutionIds.join(', ')})`);
    isLoading.set(true);
    globalError.set(null);
    cancelStream(); // Cancel any previous stream
    streamController = new AbortController();

    const requestBody: StreamRunRequest = {
        thread_id: threadId,
        input: { type: 'human', content: userInput },
        constitution_ids: constitutionIds,
    };

    try {
        await fetchEventSource(`${BASE_URL}/runs/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify(requestBody),
            signal: streamController.signal,
            openWhenHidden: true, // Keep running even if tab is not focused

            onopen: async (response) => {
                if (!response.ok) {
                    let errorMsg = `SSE connection failed! Status: ${response.status}`;
                     try {
                        const errorBody = await response.json(); // Or .text() if not json
                        errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
                    } catch (e) { /* Ignore */ }
                    throw new Error(errorMsg); // Throw to trigger onerror
                }
                console.log('SSE stream opened (run)');
                // isLoading is already true
            },

            onmessage: (event) => {
                handleSSEMessage(event);
            },

            onclose: () => {
                console.log('SSE stream closed (run).');
                isLoading.set(false);
                streamController = null;
                 // Potentially refresh thread list if a new thread was used and ended cleanly
                // fetchThreads(); // Consider if needed or handled by 'end' event logic
            },

            onerror: (err) => {
                console.error('SSE stream error (run):', err);
                isLoading.set(false);
                globalError.set(`Stream connection error: ${err.message || 'Unknown stream error'}`);
                streamController = null;
                // Important: Rethrowing the error will stop the EventSource from automatically reconnecting.
                // If you want reconnection attempts, return a time in ms or omit the throw.
                // For now, let's stop on error.
                throw err;
            },
        });
    } catch (error) {
         // Catch errors thrown from onopen or onerror to prevent unhandled promise rejections
         if (!streamController?.signal.aborted) { // Avoid logging error if it was aborted intentionally
             console.error("fetchEventSource (run) failed:", error);
             isLoading.set(false); // Ensure loading stops
             globalError.set(`Stream setup failed: ${error}`);
             streamController = null;
         } else {
             console.log("Stream intentionally aborted.");
         }
    }
};


// Stream for 'compare' mode
export const streamCompareRun = async (
    userInput: string,
    compareSetsConfig: CompareSet[]
): Promise<void> => {
    console.log(`API: streamCompareRun connecting (${compareSetsConfig.length} sets)`);
    isLoading.set(true);
    globalError.set(null);
    cancelStream(); // Cancel any previous stream
    streamController = new AbortController();

    const requestBody: CompareRunRequest = {
        input: { type: 'human', content: userInput },
        constitution_sets: compareSetsConfig,
    };

    try {
        await fetchEventSource(`${BASE_URL}/runs/compare/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            },
            body: JSON.stringify(requestBody),
            signal: streamController.signal,
            openWhenHidden: true,

            onopen: async (response) => {
                if (!response.ok) {
                     let errorMsg = `SSE connection failed! Status: ${response.status}`;
                     try {
                        const errorBody = await response.json();
                        errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
                    } catch (e) { /* Ignore */ }
                    throw new Error(errorMsg);
                }
                console.log('SSE stream opened (compare)');
            },

            onmessage: (event) => {
                 handleSSEMessage(event); // Use the same handler
            },

            onclose: () => {
                console.log('SSE stream closed (compare).');
                isLoading.set(false);
                streamController = null;
            },

            onerror: (err) => {
                console.error('SSE stream error (compare):', err);
                isLoading.set(false);
                globalError.set(`Stream connection error: ${err.message || 'Unknown stream error'}`);
                streamController = null;
                throw err; // Stop retries
            },
        });
    } catch (error) {
         if (!streamController?.signal.aborted) {
             console.error("fetchEventSource (compare) failed:", error);
             isLoading.set(false);
             globalError.set(`Stream setup failed: ${error}`);
             streamController = null;
         } else {
             console.log("Stream intentionally aborted.");
         }
    }
};
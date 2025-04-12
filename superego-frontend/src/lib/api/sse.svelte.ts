import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { logExecution, deepClone } from '../utils/utils';
import { threadStore } from '$lib/state/threads.svelte';
import { activeStore } from '$lib/state/active.svelte'; 
import { sessionStore } from '../state/session.svelte';
import { getLatestHistory } from './rest.svelte'; 

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Stream Processing Logic ---

/**
 * Mutates the entry by appending text content from a 'chunk' event.
 * Creates a new AI message if the node changes.
 */
function handleChunk(entryToMutate: HistoryEntry, chunkData: SSEChunkData): void {
    const messages = entryToMutate.values.messages;

    // Create new AI message if node changes or message list is empty
    if (messages.at(-1)?.nodeId !== chunkData.node) {
        messages.push({
            type: 'ai',
            content: '',
            nodeId: chunkData.node,
            tool_calls: [] // Initialize tool_calls for potential subsequent tool chunks
        });
    }

    const lastMessage = messages.at(-1);
    // Append content if last message is AI and from the same node
    if (lastMessage && lastMessage.type === 'ai') {
         if (typeof lastMessage.content !== 'string') {
            console.warn("Appending chunk to non-string AI content, converting existing content.");
            lastMessage.content = String(lastMessage.content);
         }
         lastMessage.content += chunkData.content;
    // Handle unexpected case: chunk received after non-AI message from same node
    } else if (lastMessage) {
         messages.push({
            type: 'ai',
            content: chunkData.content,
            nodeId: chunkData.node,
            tool_calls: []
        });
        console.warn("Received chunk after non-AI message from same node. Creating new AI message.");
    }
}

/**
 * Mutates the entry by adding/updating tool call info from an 'ai_tool_chunk' event.
 * Creates a new AI message if the node changes.
 */
function handleToolChunk(entryToMutate: HistoryEntry, toolChunkData: SSEToolCallChunkData): void {
    const messages = entryToMutate.values.messages;
    let lastMessage = messages.at(-1);

    // Create new AI message if node changes or message list is empty
    if (!lastMessage || lastMessage.nodeId !== toolChunkData.node) {
        const newAiMessage: AiApiMessage = {
            type: 'ai',
            content: '',
            nodeId: toolChunkData.node,
            tool_calls: []
        };
        messages.push(newAiMessage);
        lastMessage = newAiMessage;
    // Handle unexpected case: tool chunk received after non-AI message from same node
    } else if (lastMessage.type !== 'ai') {
         const newAiMessage: AiApiMessage = {
            type: 'ai',
            content: '',
            nodeId: toolChunkData.node,
            tool_calls: []
        };
        messages.push(newAiMessage);
        lastMessage = newAiMessage;
        console.warn("Received ai_tool_chunk after non-AI message from same node. Creating new AI message.");
    }

    if (!lastMessage.tool_calls) {
        lastMessage.tool_calls = [];
    }

    // If 'id' is present, start a new tool call structure
    if (toolChunkData.id) {
        lastMessage.tool_calls.push({
            id: toolChunkData.id,
            name: toolChunkData.name || '',
            args: toolChunkData.args || ''
        });
    } else if (toolChunkData.args && lastMessage.tool_calls.length > 0) {
        // If only 'args' are present, append to the *last* tool call's args
        // If only args are present, append to the args of the *last* tool call in the array
        const lastToolCall = lastMessage.tool_calls.at(-1);
        if (lastToolCall) {
            lastToolCall.args += toolChunkData.args;
        } else {
             console.error("Received tool chunk args, but no existing tool call structure found on the message.", lastMessage);
        }
    }
     // Ignore chunks with neither id nor args for now.
     // Ignore chunks with neither id nor args? Or log warning? For now, ignore.
}

/**
 * Mutates the entry by adding a ToolApiMessage based on a 'tool_result' event.
 */
function handleToolResult(entryToMutate: HistoryEntry, toolResultData: SSEToolResultData): void {
    // Construct the ToolApiMessage directly from the SSE event data fields.
    // Assumes toolResultData contains the necessary fields like content, tool_name, tool_call_id, node, is_error.
    // We no longer use the faulty parseToolResultString utility.

    const newToolMessage: ToolApiMessage = {
    	type: 'tool',
    	content: toolResultData.content ?? '',
    	tool_call_id: String(toolResultData.tool_call_id ?? ''),
    	name: toolResultData.tool_name,
    	nodeId: toolResultData.node,
    	is_error: toolResultData.is_error
    };

    entryToMutate.values.messages.push(newToolMessage);
}


// --- SSE Event Handlers ---

function handleRunStartEvent(
    startData: SSERunStartData,
    currentActiveSessionId: string,
    threadIdToSend: string | null // This is the ID we *sent* the request with (null if new)
) {
    const targetThreadId = startData.thread_id; // This is the ID the backend *confirmed* or created

    // Direct mutation for $state variable
    // Determine initial messages based on existing cache if present
    const existingEntry = threadStore.threadCacheStore[targetThreadId]; // Use threadStore
    let updatedMessages: MessageType[];
    if (existingEntry?.history?.values?.messages) {
        const existingMessages = existingEntry.history.values.messages;
        const newMessages = startData.initialMessages.filter(
            newMsg => !existingMessages.some(existingMsg =>
                existingMsg.type === newMsg.type && existingMsg.content === newMsg.content
            )
        );
        updatedMessages = [...existingMessages, ...newMessages];
    } else {
        updatedMessages = startData.initialMessages;
    }

    // Create the new/updated cache entry data
    const newCacheEntry: ThreadCacheData = {
        history: {
            checkpoint_id: existingEntry?.history?.checkpoint_id || '',
            thread_id: targetThreadId,
            values: { messages: updatedMessages },
            runConfig: startData.runConfig
        },
        isStreaming: true,
        error: null
    };

    // Use the setter function to update the cache store
    threadStore.setEntry(targetThreadId, newCacheEntry); // Use threadStore.setEntry

    // If this run started a *new* thread (threadIdToSend was null), update session/known IDs
    if (threadIdToSend === null) {
        console.log(`Received run_start for new thread ID: ${targetThreadId} for session ${currentActiveSessionId}`);
        sessionStore.addKnownThreadId(targetThreadId); // Call method on sessionStore instance
        sessionStore.addThreadToSession(currentActiveSessionId, targetThreadId); // Call method on sessionStore instance
    } else if (threadIdToSend !== targetThreadId) {
        // This case shouldn't happen with current backend logic but good to log
        console.warn(`run_start thread ID ${targetThreadId} differs from requested thread ID ${threadIdToSend}`);
    }
}

function handleStreamUpdateEvent(
    eventType: 'chunk' | 'ai_tool_chunk' | 'tool_result',
    eventData: SSEChunkData | SSEToolCallChunkData | SSEToolResultData,
    targetThreadId: string
) {
    // Direct access to $state variable is correct here for reading
    const currentCache = threadStore.threadCacheStore; // Use threadStore
    const currentCacheEntry = currentCache[targetThreadId];

    if (!currentCacheEntry) {
        console.error(`Received '${eventType}' for thread ${targetThreadId}, but no cache entry found. Was 'run_start' missed?`);
        return;
    }

    if (!currentCacheEntry.isStreaming || currentCacheEntry.error) {
        console.warn(`Ignoring '${eventType}' for thread ${targetThreadId} because stream is not active or has an error.`);
        return;
    }

    const historyToMutate = deepClone(currentCacheEntry.history!);
    try {
        if (eventType === 'chunk') {
            handleChunk(historyToMutate, eventData as SSEChunkData);
        } else if (eventType === 'ai_tool_chunk') {
            handleToolChunk(historyToMutate, eventData as SSEToolCallChunkData);
        } else {
            handleToolResult(historyToMutate, eventData as SSEToolResultData);
        }

        // Use the update function for the specific entry
        threadStore.updateEntry(targetThreadId, { history: historyToMutate }); // Use threadStore.updateEntry
    } catch (processingError: unknown) {
         console.error(`Error processing '${eventType}' in streamProcessor:`, processingError);
         activeStore.setGlobalError(`Error processing '${eventType}' in streamProcessor: ${processingError instanceof Error ? processingError.message : String(processingError)}`); // Use activeStore.setGlobalError
    }
}

function handleErrorEvent(
    errorData: SSEErrorData,
    targetThreadId: string | null
) {
    const errorMessage = `Backend Error (${errorData.node}): ${errorData.error}`;
    console.error(`SSE Error Event Received (Thread: ${targetThreadId ?? 'N/A'}):`, errorMessage);
    activeStore.setGlobalError(errorMessage); // Use activeStore.setGlobalError

    // Update cache entry if threadId exists
    if (targetThreadId) {
        // Use update function for the specific entry
        threadStore.updateEntry(targetThreadId, { isStreaming: false, error: errorMessage }); // Use threadStore.updateEntry
    }
}

async function handleEndEvent(
    endData: SSEEndData,
    targetThreadId: string,
    controller: AbortController
) {
    console.log(`SSE stream ended for thread ${targetThreadId}. Final Checkpoint: ${endData.checkpoint_id}`);
    try {
        const finalHistoryEntry = await getLatestHistory(targetThreadId, controller.signal);

        // Use update function for the specific entry
        threadStore.updateEntry(targetThreadId, { history: finalHistoryEntry, isStreaming: false, error: null }); // Use threadStore.updateEntry
        console.log(`Cache updated with final state for thread ${targetThreadId}`);
    } catch (fetchError: unknown) {
         if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) {
             console.error(`Failed to fetch final history for thread ${targetThreadId}:`, fetchError);
             activeStore.setGlobalError(`Failed to fetch final state: ${fetchError instanceof Error ? fetchError.message : String(fetchError)}`); // Use activeStore.setGlobalError
         }
    }
}

const eventHandlers: { [key: string]: Function } = {
    'run_start': handleRunStartEvent,
    'chunk': handleStreamUpdateEvent,
    'ai_tool_chunk': handleStreamUpdateEvent,
    'tool_result': handleStreamUpdateEvent,
    'error': handleErrorEvent,
    'end': handleEndEvent
};

/**
 * Initiates a stream run for the active session.
 * Handles sending the request with CheckpointConfigurable and processing SSE events.
 * Updates the historyCacheStore directly.
 */
export const streamRun = async (
    userInput: string,
    runConfig: RunConfig,
    threadId: string | null
): Promise<AbortController> => {
    activeStore.clearGlobalError(); // Use activeStore.clearGlobalError
    const controller = new AbortController();
    // Access .state for persisted store
    const currentActiveSessionId = sessionStore.activeSessionId; // Use new session state

    if (!currentActiveSessionId) {
        const errorMsg = "Cannot start run: No active session selected.";
        console.error(errorMsg);
        activeStore.setGlobalError(errorMsg); // Use activeStore.setGlobalError
        controller.abort();
        return controller;
    }

    // Access .state for persisted store
    const currentSessionData = sessionStore.uiSessions[currentActiveSessionId]; // Use new session state (renamed variable to avoid conflict)
    if (!currentSessionData) {
        const errorMsg = `Cannot start run: Active session state not found for ID ${currentActiveSessionId}.`;
        console.error(errorMsg);
        activeStore.setGlobalError(errorMsg); // Use activeStore.setGlobalError
        controller.abort();
        return controller;
    }

    const threadIdToSend: string | null = threadId;
    const checkpointConfigurable: CheckpointConfigurable = {
        thread_id: threadIdToSend,
        runConfig: runConfig,
    };

    const requestBody = {
        input: { type: 'human', content: userInput },
        configurable: checkpointConfigurable,
    };

    logExecution(`Stream run for session ${currentActiveSessionId} (Thread: ${threadIdToSend ?? 'NEW'})`, async () => {
        try {
            await fetchEventSource(`${BASE_URL}/runs/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
                body: JSON.stringify(requestBody),
                signal: controller.signal,
                openWhenHidden: true,

                onopen: async (response) => {
                    if (!response.ok) {
                        let errorMsg = `SSE connection failed! Status: ${response.status}`;
                        try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ }
                        activeStore.setGlobalError(`Connection Error: ${errorMsg}`); // Use activeStore.setGlobalError
                        throw new Error(errorMsg);
                    }
                    console.log(`SSE stream opened for session ${currentActiveSessionId}`);
                },

                onmessage: (event: EventSourceMessage) => {
                    try {
                        if (!event.data) { console.warn('SSE message received with no data.'); return; }
                        const parsedEvent: SSEEventData = JSON.parse(event.data);
                        const eventType = parsedEvent.type;
                        const eventData = parsedEvent.data;
                        const eventThreadId = parsedEvent.thread_id;

                        const targetThreadId = eventThreadId || threadIdToSend;

                        // Allow 'error' events even if targetThreadId is somehow null
                        if (!targetThreadId && eventType !== 'error') {
                            console.error(`SSE event type '${eventType}' received without a usable thread_id. Cannot process.`, parsedEvent);
                            activeStore.setGlobalError(`System Error: Event '${eventType}' missing thread_id.`); // Use activeStore.setGlobalError
                            return;
                        }

                        const handler = eventHandlers[eventType];
                        if (handler) {
                            // Call the appropriate handler, passing necessary context
                            if (eventType === 'run_start') {
                                handler(eventData as SSERunStartData, currentActiveSessionId, threadIdToSend);
                            } else if (eventType === 'chunk' || eventType === 'ai_tool_chunk' || eventType === 'tool_result') {
                                if (targetThreadId) {
                                    handler(eventType, eventData as any, targetThreadId); // Pass eventType to combined handler
                                } else {
                                     console.error(`Cannot process '${eventType}' without targetThreadId.`, parsedEvent);
                                     activeStore.setGlobalError(`System Error: Cannot process '${eventType}' without thread ID.`); // Use activeStore.setGlobalError
                                }
                            } else if (eventType === 'error') {
                                handler(eventData as SSEErrorData, targetThreadId); // Pass potentially null targetThreadId
                            } else if (eventType === 'end') {
                                if (targetThreadId) {
                                    // Call async handler but don't await; handle promise rejection
                                    Promise.resolve(handler(eventData as SSEEndData, targetThreadId, controller))
                                        .catch(err => {
                                            console.error("Error in async end handler:", err);
                                            activeStore.setGlobalError("Error finalizing stream state."); // Use activeStore.setGlobalError
                                        });
                                } else {
                                     console.error(`Cannot process 'end' without targetThreadId.`, parsedEvent);
                                     activeStore.setGlobalError(`System Error: Cannot process 'end' without thread ID.`); // Use activeStore.setGlobalError
                                }
                            }
                        } else {
                            console.warn('Unhandled SSE event type:', eventType, parsedEvent);
                        }
                    } catch (error: unknown) {
                        console.error('Failed to parse or handle SSE message data:', event.data, error);
                        activeStore.setGlobalError(`Failed to process message: ${error instanceof Error ? error.message : String(error)}`); // Use activeStore.setGlobalError
                    }
                },

                onclose: () => {
                    console.log(`SSE stream closed for session ${currentActiveSessionId}.`);
                },

                onerror: (err) => {
                    if (controller.signal.aborted) { return; }
                    console.error(`SSE stream error for session ${currentActiveSessionId}:`, err);
                    const errorMsg = err instanceof Error ? err.message : String(err);
                    activeStore.setGlobalError(`Stream Error: ${errorMsg}`); // Use activeStore.setGlobalError
                    // Don't throw from onerror, allow graceful closure.
                },
            });
        } catch (error) {
            // Catches errors from fetchEventSource setup or onopen.
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                console.error(`Error setting up SSE stream for session ${currentActiveSessionId}:`, error);
                // globalError is likely already set by onopen or apiFetch, but set again just in case
                activeStore.setGlobalError(`Stream Setup Error: ${error instanceof Error ? error.message : String(error)}`); // Use activeStore.setGlobalError
            }
        }
    });

    return controller;
};
// import { get } from 'svelte/store'; // Removed
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { logExecution, deepClone } from '../utils';
import { globalError, setGlobalError, threadCacheStore, updateThreadCacheEntry, setThreadCacheEntry, persistedActiveSessionId, persistedUiSessions } from '../stores.svelte'; // Import state and setters
import { addThreadToSession, addKnownThreadId } from '../sessionManager';
import { handleChunk, handleToolChunk, handleToolResult } from '../streamProcessor';
import { getLatestHistory } from '../api';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- SSE Event Handlers ---

function handleRunStartEvent(
    startData: SSERunStartData,
    currentActiveSessionId: string,
    threadIdToSend: string | null // This is the ID we *sent* the request with (null if new)
) {
    const targetThreadId = startData.thread_id; // This is the ID the backend *confirmed* or created

    // Direct mutation for $state variable
    // Determine initial messages based on existing cache if present
    const existingEntry = threadCacheStore[targetThreadId];
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
    setThreadCacheEntry(targetThreadId, newCacheEntry);

    // If this run started a *new* thread (threadIdToSend was null), update session/known IDs
    if (threadIdToSend === null) {
        console.log(`Received run_start for new thread ID: ${targetThreadId} for session ${currentActiveSessionId}`);
        addKnownThreadId(targetThreadId);
        addThreadToSession(currentActiveSessionId, targetThreadId);
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
    const currentCache = threadCacheStore;
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
        updateThreadCacheEntry(targetThreadId, { history: historyToMutate });
    } catch (processingError: unknown) {
         console.error(`Error processing '${eventType}' in streamProcessor:`, processingError);
         setGlobalError(`Error processing '${eventType}' in streamProcessor: ${processingError instanceof Error ? processingError.message : String(processingError)}`);
    }
}

function handleErrorEvent(
    errorData: SSEErrorData,
    targetThreadId: string | null
) {
    const errorMessage = `Backend Error (${errorData.node}): ${errorData.error}`;
    console.error(`SSE Error Event Received (Thread: ${targetThreadId ?? 'N/A'}):`, errorMessage);
    setGlobalError(errorMessage); // Correctly uses setter

    // Update cache entry if threadId exists
    if (targetThreadId) {
        // Use update function for the specific entry
        updateThreadCacheEntry(targetThreadId, { isStreaming: false, error: errorMessage });
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
        updateThreadCacheEntry(targetThreadId, { history: finalHistoryEntry, isStreaming: false, error: null });
        console.log(`Cache updated with final state for thread ${targetThreadId}`);
    } catch (fetchError: unknown) {
         if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) {
             console.error(`Failed to fetch final history for thread ${targetThreadId}:`, fetchError);
             setGlobalError(`Failed to fetch final state: ${fetchError instanceof Error ? fetchError.message : String(fetchError)}`); // Correctly uses setter
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
    setGlobalError(null); // Correctly uses setter
    const controller = new AbortController();
    // Access .state for persisted store
    const currentActiveSessionId = persistedActiveSessionId.state; // Correctly uses .state

    if (!currentActiveSessionId) {
        const errorMsg = "Cannot start run: No active session selected.";
        console.error(errorMsg);
        setGlobalError(errorMsg); // Correctly uses setter
        controller.abort();
        return controller;
    }

    // Access .state for persisted store
    const sessionState = persistedUiSessions.state[currentActiveSessionId]; // Correctly uses .state
    if (!sessionState) {
        const errorMsg = `Cannot start run: Active session state not found for ID ${currentActiveSessionId}.`;
        console.error(errorMsg);
        setGlobalError(errorMsg); // Correctly uses setter
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
                        setGlobalError(`Connection Error: ${errorMsg}`); // Correctly uses setter
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
                            setGlobalError(`System Error: Event '${eventType}' missing thread_id.`); // Correctly uses setter
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
                                     setGlobalError(`System Error: Cannot process '${eventType}' without thread ID.`); // Correctly uses setter
                                }
                            } else if (eventType === 'error') {
                                handler(eventData as SSEErrorData, targetThreadId); // Pass potentially null targetThreadId
                            } else if (eventType === 'end') {
                                if (targetThreadId) {
                                    // Call async handler but don't await; handle promise rejection
                                    Promise.resolve(handler(eventData as SSEEndData, targetThreadId, controller))
                                        .catch(err => {
                                            console.error("Error in async end handler:", err);
                                            setGlobalError("Error finalizing stream state."); // Correctly uses setter
                                        });
                                } else {
                                     console.error(`Cannot process 'end' without targetThreadId.`, parsedEvent);
                                     setGlobalError(`System Error: Cannot process 'end' without thread ID.`); // Correctly uses setter
                                }
                            }
                        } else {
                            console.warn('Unhandled SSE event type:', eventType, parsedEvent);
                        }
                    } catch (error: unknown) {
                        console.error('Failed to parse or handle SSE message data:', event.data, error);
                        setGlobalError(`Failed to process message: ${error instanceof Error ? error.message : String(error)}`); // Correctly uses setter
                    }
                },

                onclose: () => {
                    console.log(`SSE stream closed for session ${currentActiveSessionId}.`);
                },

                onerror: (err) => {
                    if (controller.signal.aborted) { return; }
                    console.error(`SSE stream error for session ${currentActiveSessionId}:`, err);
                    const errorMsg = err instanceof Error ? err.message : String(err);
                    setGlobalError(`Stream Error: ${errorMsg}`); // Correctly uses setter
                    // Don't throw from onerror, allow graceful closure.
                },
            });
        } catch (error) {
            // Catches errors from fetchEventSource setup or onopen.
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                console.error(`Error setting up SSE stream for session ${currentActiveSessionId}:`, error);
                // globalError is likely already set by onopen or apiFetch, but set again just in case
                setGlobalError(`Stream Setup Error: ${error instanceof Error ? error.message : String(error)}`); // Correctly uses setter
            }
        }
    });

    return controller;
};
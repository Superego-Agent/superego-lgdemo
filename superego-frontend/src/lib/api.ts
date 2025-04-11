import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { logExecution, deepClone } from './utils';
import { globalError, threadCacheStore } from './stores'; 
import { uiSessions, knownThreadIds, activeSessionId } from './stores';
import { addThreadToSession, addKnownThreadId } from './sessionManager';
import { handleChunk, handleToolChunk, handleToolResult } from './streamProcessor';
// Types from global.d.ts are globally available.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
    globalError.set(null);

    try {
        const response = await fetch(url, {
            ...options,
            signal,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try {
                const errorText = await response.text();
                try {
                    const errorBody = JSON.parse(errorText);
                    errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`;
                } catch (parseError) {
                    errorMsg += ` - ${errorText}`;
                }
            } catch (e) { /* Ignore */ }
            throw new Error(errorMsg);
        }

        if (response.status === 204) {
            return undefined as T;
        }

        return await response.json() as T;

    } catch (error: unknown) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
            console.error('API Fetch Error:', url, error);
            const errorMsg = error instanceof Error ? error.message : String(error);
            globalError.set(errorMsg || 'An unknown API error occurred.');
            throw error;
        } else {
            console.log('API Fetch aborted:', url);
            throw error;
        }
    }
}



/**
 * Fetches the latest history entry (state) for a given thread.
 */
export const getLatestHistory = (threadId: string, signal?: AbortSignal): Promise<HistoryEntry> => {
    return logExecution(`Fetch latest history for thread ${threadId}`, () =>
        apiFetch<HistoryEntry>(`${BASE_URL}/threads/${threadId}/latest`, {}, signal)
    );
};

/**
 * Fetches all relevant history entries for a given thread.
 */
export const getFullHistory = (threadId: string, signal?: AbortSignal): Promise<HistoryEntry[]> => {
    return logExecution(`Fetch full history for thread ${threadId}`, () =>
        apiFetch<HistoryEntry[]>(`${BASE_URL}/threads/${threadId}/history`, {}, signal)
    );
};

/**
 * Fetches the list of available global constitutions.
 * Assumes the backend provides an endpoint like /api/constitutions.
 */
export const fetchAvailableConstitutions = (signal?: AbortSignal): Promise<ConstitutionItem[]> => {
    return logExecution('Fetch available constitutions', () =>
        apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`, {}, signal)
    );
};

/**
 * Fetches the full text content of a specific global constitution.
 * Assumes the backend provides an endpoint like /api/constitutions/{constitution_id}/content.
 */
export const fetchConstitutionContent = (constitutionId: string, signal?: AbortSignal): Promise<string> => {
    return logExecution(`Fetch content for constitution ${constitutionId}`, async () => {
        // Assuming the endpoint returns plain text
        globalError.set(null);
        try {
            // Note: apiFetch assumes JSON response, so use raw fetch here for text/plain
            const response = await fetch(`${BASE_URL}/constitutions/${constitutionId}/content`, {
                signal,
                headers: { 'Accept': 'text/plain' }, // Request plain text
            });
            if (!response.ok) {
                let errorMsg = `HTTP error! Status: ${response.status}`;
                try { const errorText = await response.text(); errorMsg += ` - ${errorText}`; } catch (e) { /* Ignore */ }
                throw new Error(errorMsg);
            }
            return await response.text();
        } catch (error: unknown) {
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                console.error(`API Fetch Error (Text): ${BASE_URL}/constitutions/${constitutionId}/content`, error);
                const errorMsg = error instanceof Error ? error.message : String(error);
                globalError.set(errorMsg || 'An unknown API error occurred fetching constitution content.');
                throw error;
            } else {
                console.log(`API Fetch aborted: ${BASE_URL}/constitutions/${constitutionId}/content`);
                throw error;
            }
        }
    });
};


/**
 * Submits a new constitution for review.
 * Assumes the backend provides a POST endpoint like /api/constitutions.
 */
export const submitConstitution = (
    payload: ConstitutionSubmission,
    signal?: AbortSignal
): Promise<SubmissionResponse> => {
    return logExecution('Submit constitution for review', () =>
        apiFetch<SubmissionResponse>(`${BASE_URL}/constitutions`, {
            method: 'POST',
            body: JSON.stringify(payload),
        }, signal)
    );
};




function handleRunStartEvent(
    startData: SSERunStartData,
    currentActiveSessionId: string,
    threadIdToSend: string | null // This is the ID we *sent* the request with (null if new)
) {
    const targetThreadId = startData.thread_id; // This is the ID the backend *confirmed* or created

    threadCacheStore.update(cache => {
        const existingEntry = cache[targetThreadId];
        let updatedMessages: MessageType[];

        if (existingEntry?.history?.values?.messages) {
            // Preserve existing messages and append initial messages from run_start
            // Ensure no duplicates if initialMessages contains the user input already present
            const existingMessages = existingEntry.history.values.messages;
            const newMessages = startData.initialMessages.filter(
                newMsg => !existingMessages.some(existingMsg =>
                    // Basic duplicate check (might need refinement based on message IDs if available)
                    existingMsg.type === newMsg.type && existingMsg.content === newMsg.content
                )
            );
            updatedMessages = [...existingMessages, ...newMessages];
        } else {
            // No existing entry or messages, use initial messages directly
            updatedMessages = startData.initialMessages;
        }

        const updatedCacheData: ThreadCacheData = {
            // Use existing history structure if available, otherwise create new
            history: {
                checkpoint_id: existingEntry?.history?.checkpoint_id || '', // Preserve old checkpoint ID until 'end'
                thread_id: targetThreadId,
                values: { messages: updatedMessages },
                runConfig: startData.runConfig // Update runConfig from the start event
            },
            isStreaming: true,
            error: null // Clear any previous error
        };

        return {
            ...cache,
            [targetThreadId]: updatedCacheData
        };
    });

    // If this run started a *new* thread (threadIdToSend was null), update session/known IDs
    if (threadIdToSend === null) {
        console.log(`Received run_start for new thread ID: ${targetThreadId} for session ${currentActiveSessionId}`);
        addKnownThreadId(targetThreadId);
        addThreadToSession(currentActiveSessionId, targetThreadId);
    } else if (threadIdToSend !== targetThreadId) {
        // This case shouldn't happen with current backend logic but good to log
        console.warn(`run_start thread ID ${targetThreadId} differs from requested thread ID ${threadIdToSend}`);
        // Potentially update session mapping if needed, though backend should handle thread continuity
    }
}

function handleStreamUpdateEvent(
    eventType: 'chunk' | 'ai_tool_chunk' | 'tool_result',
    eventData: SSEChunkData | SSEToolCallChunkData | SSEToolResultData,
    targetThreadId: string
) {
    const currentCache = get(threadCacheStore);
    const currentCacheEntry = currentCache[targetThreadId];

    if (!currentCacheEntry) {
        console.error(`Received '${eventType}' for thread ${targetThreadId}, but no cache entry found. Was 'run_start' missed?`);
        // Don't set globalError here, let the stream continue if possible, maybe run_start is delayed
        // globalError.set(`System Error: State mismatch for thread ${targetThreadId}.`);
        return; // Cannot process without a cache entry
    }

    // Ensure we don't process updates if there was a prior error or stream ended prematurely
    if (!currentCacheEntry.isStreaming || currentCacheEntry.error) {
        console.warn(`Ignoring '${eventType}' for thread ${targetThreadId} because stream is not active or has an error.`);
        return;
    }

    // Clone the history part for mutation, keep other flags
    // We've already checked that currentCacheEntry exists, isStreaming is true, and error is null.
    // This implies currentCacheEntry.history cannot be null here. Use type assertion (!) to inform TS.
    const historyToMutate = deepClone(currentCacheEntry.history!);
    try {
        if (eventType === 'chunk') {
            handleChunk(historyToMutate, eventData as SSEChunkData);
        } else if (eventType === 'ai_tool_chunk') {
            handleToolChunk(historyToMutate, eventData as SSEToolCallChunkData);
        } else {
            handleToolResult(historyToMutate, eventData as SSEToolResultData);
        }

        // Update the cache entry with mutated history, keeping streaming true
        threadCacheStore.update(cache => ({
            ...cache,
            [targetThreadId]: {
                ...currentCacheEntry, // Keep existing flags like isStreaming, error
                history: historyToMutate
            }
        }));
    } catch (processingError: unknown) {
         console.error(`Error processing '${eventType}' in streamProcessor:`, processingError);
         globalError.set(`Error updating state for ${eventType}: ${processingError instanceof Error ? processingError.message : String(processingError)}`);
    }
}

function handleErrorEvent(
    errorData: SSEErrorData,
    targetThreadId: string | null
) {
    const errorMessage = `Backend Error (${errorData.node}): ${errorData.error}`;
    console.error(`SSE Error Event Received (Thread: ${targetThreadId ?? 'N/A'}):`, errorMessage);
    globalError.set(errorMessage);

    // Update cache entry if threadId exists
    if (targetThreadId) {
        threadCacheStore.update(cache => {
            const entry = cache[targetThreadId];
            if (entry) {
                return {
                    ...cache,
                    [targetThreadId]: {
                        ...entry,
                        isStreaming: false,
                        error: errorMessage
                    }
                };
            }
            // If no entry exists yet, create one to store the error
            return {
                ...cache,
                [targetThreadId]: {
                    history: null, // No history available
                    isStreaming: false,
                    error: errorMessage
                }
            };
        });
    }
}

// Async handler for the 'end' event
async function handleEndEvent(
    endData: SSEEndData,
    targetThreadId: string,
    controller: AbortController
) {
    console.log(`SSE stream ended for thread ${targetThreadId}. Final Checkpoint: ${endData.checkpoint_id}`);
    try {
        // Fetch the definitive final state
        const finalHistoryEntry = await getLatestHistory(targetThreadId, controller.signal);

        // Update the cache entry with final state, mark streaming as false, clear error
        threadCacheStore.update(cache => {
             const currentEntry = cache[targetThreadId];
             return {
                ...cache,
                [targetThreadId]: {
                    // Preserve existing data if fetch somehow failed, but mark as not streaming
                    ...(currentEntry ?? {}),
                    history: finalHistoryEntry, // Overwrite with definitive final state
                    isStreaming: false,
                    error: null // Clear any previous transient errors
                }
             };
        });
        console.log(`Cache updated with final state for thread ${targetThreadId}`);
    } catch (fetchError: unknown) {
         if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) {
             console.error(`Failed to fetch final history for thread ${targetThreadId}:`, fetchError);
             globalError.set(`Failed to fetch final state: ${fetchError instanceof Error ? fetchError.message : String(fetchError)}`);
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
    globalError.set(null);
    const controller = new AbortController();
    const currentActiveSessionId = get(activeSessionId);

    if (!currentActiveSessionId) {
        const errorMsg = "Cannot start run: No active session selected.";
        console.error(errorMsg);
        globalError.set(errorMsg);
        controller.abort();
        return controller;
    }

    const sessionState = get(uiSessions)[currentActiveSessionId];
    if (!sessionState) {
        const errorMsg = `Cannot start run: Active session state not found for ID ${currentActiveSessionId}.`;
        console.error(errorMsg);
        globalError.set(errorMsg);
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
                        globalError.set(`Connection Error: ${errorMsg}`);
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
                            globalError.set(`System Error: Event '${eventType}' missing thread_id.`);
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
                                     globalError.set(`System Error: Cannot process '${eventType}' without thread ID.`);
                                }
                            } else if (eventType === 'error') {
                                handler(eventData as SSEErrorData, targetThreadId); // Pass potentially null targetThreadId
                            } else if (eventType === 'end') {
                                if (targetThreadId) {
                                    // Call async handler but don't await; handle promise rejection
                                    Promise.resolve(handler(eventData as SSEEndData, targetThreadId, controller))
                                        .catch(err => {
                                            console.error("Error in async end handler:", err);
                                            globalError.set("Error finalizing stream state.");
                                        });
                                } else {
                                     console.error(`Cannot process 'end' without targetThreadId.`, parsedEvent);
                                     globalError.set(`System Error: Cannot process 'end' without thread ID.`);
                                }
                            }
                        } else {
                            console.warn('Unhandled SSE event type:', eventType, parsedEvent);
                        }
                    } catch (error: unknown) {
                        console.error('Failed to parse or handle SSE message data:', event.data, error);
                        globalError.set(`Failed to process message: ${error instanceof Error ? error.message : String(error)}`);
                    }
                },

                onclose: () => {
                    console.log(`SSE stream closed for session ${currentActiveSessionId}.`);
                },

                onerror: (err) => {
                    if (controller.signal.aborted) { return; }
                    console.error(`SSE stream error for session ${currentActiveSessionId}:`, err);
                    const errorMsg = err instanceof Error ? err.message : String(err);
                    globalError.set(`Stream Error: ${errorMsg}`);
                    // Don't throw from onerror, allow graceful closure.
                },
            });
        } catch (error) {
            // Catches errors from fetchEventSource setup or onopen.
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                console.error(`Error setting up SSE stream for session ${currentActiveSessionId}:`, error);
                // globalError is likely already set by onopen or apiFetch, but set again just in case
                globalError.set(`Stream Setup Error: ${error instanceof Error ? error.message : String(error)}`);
            }
        }
    });

    return controller;
};


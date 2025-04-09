// src/lib/api.ts
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { logExecution, deepClone } from './utils';
import { globalError, historyCacheStore } from './stores';
import { uiSessions, knownThreadIds, activeSessionId } from './stores';
import { addThreadToSession, addKnownThreadId } from './sessionManager';
import { handleChunk, handleToolChunk, handleToolResult } from './streamProcessor';
// Types from global.d.ts are globally available.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Core API Fetch Helper (Simplified) ---
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


// --- New API Functions ---

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


// --- Stream Run Function ---

// --- Event Handler Functions ---

function handleRunStartEvent(
    startData: SSERunStartData,
    currentActiveSessionId: string,
    threadIdToSend: string | null
) {
    const initialEntry: HistoryEntry = {
        checkpoint_id: '',
        thread_id: startData.thread_id,
        values: { messages: startData.initialMessages },
        runConfig: startData.runConfig
    };
    historyCacheStore.update(cache => ({
        ...cache,
        [startData.thread_id]: initialEntry
    }));
    if (threadIdToSend === null) {
        console.log(`Received run_start for new thread ID: ${startData.thread_id} for session ${currentActiveSessionId}`);
        addKnownThreadId(startData.thread_id);
        addThreadToSession(currentActiveSessionId, startData.thread_id);
    }
}

function handleThreadInfoEvent(
    threadInfo: SSEThreadInfoData,
    currentActiveSessionId: string,
    threadIdToSend: string | null
) {
    if (threadIdToSend === null && threadInfo.thread_id) {
         console.log(`Received thread_info confirmation for new thread ID: ${threadInfo.thread_id} for session ${currentActiveSessionId}`);
         addKnownThreadId(threadInfo.thread_id);
         addThreadToSession(currentActiveSessionId, threadInfo.thread_id);
    }
}

// Combined handler for events that update the message stream
function handleStreamUpdateEvent(
    eventType: 'chunk' | 'ai_tool_chunk' | 'tool_result',
    eventData: SSEChunkData | SSEToolCallChunkData | SSEToolResultData,
    targetThreadId: string
) {
    const currentCache = get(historyCacheStore);
    const currentEntry = currentCache[targetThreadId];

    if (!currentEntry) {
        console.error(`Received '${eventType}' for thread ${targetThreadId}, but no cache entry found. Was 'run_start' missed?`);
        globalError.set(`System Error: State mismatch for thread ${targetThreadId}.`);
        return;
    }

    const entryToMutate = deepClone(currentEntry);

    try {
        if (eventType === 'chunk') {
            handleChunk(entryToMutate, eventData as SSEChunkData);
        } else if (eventType === 'ai_tool_chunk') {
            handleToolChunk(entryToMutate, eventData as SSEToolCallChunkData);
        } else {
            handleToolResult(entryToMutate, eventData as SSEToolResultData);
        }

        historyCacheStore.update(cache => ({
            ...cache,
            [targetThreadId]: entryToMutate
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
    console.error(`SSE Error Event Received (Node: ${errorData.node}, Thread: ${targetThreadId ?? 'N/A'}):`, errorData.error);
    globalError.set(`Backend Error (${errorData.node}): ${errorData.error}`);
}

// Async handler for the 'end' event
async function handleEndEvent(
    endData: SSEEndData,
    targetThreadId: string,
    controller: AbortController
) {
    console.log(`SSE stream ended for thread ${targetThreadId}. Final Checkpoint: ${endData.checkpoint_id}`);
    try {
        const finalEntry = await getLatestHistory(targetThreadId, controller.signal);
        historyCacheStore.update(cache => ({
            ...cache,
            [targetThreadId]: finalEntry
        }));
        console.log(`Cache updated with final state for thread ${targetThreadId}`);
    } catch (fetchError: unknown) {
         if (!(fetchError instanceof DOMException && fetchError.name === 'AbortError')) {
             console.error(`Failed to fetch final history for thread ${targetThreadId}:`, fetchError);
             globalError.set(`Failed to fetch final state: ${fetchError instanceof Error ? fetchError.message : String(fetchError)}`);
         }
    }
}

// --- Event Handler Map ---
const eventHandlers: { [key: string]: Function } = {
    'run_start': handleRunStartEvent,
    'thread_info': handleThreadInfoEvent,
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
    runConfig: RunConfig
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

    const threadIdToSend: string | null = sessionState.threadIds.length > 0 ? sessionState.threadIds[0] : null;

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

                        // --- Dispatch using Handler Map ---
                        const handler = eventHandlers[eventType];
                        if (handler) {
                            // Call the appropriate handler, passing necessary context
                            if (eventType === 'run_start') {
                                handler(eventData as SSERunStartData, currentActiveSessionId, threadIdToSend);
                            } else if (eventType === 'thread_info') {
                                handler(eventData as SSEThreadInfoData, currentActiveSessionId, threadIdToSend);
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

// Removed Old Functions

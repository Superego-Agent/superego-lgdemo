// src/lib/api.ts
import { get } from 'svelte/store';
import { fetchEventSource, type EventSourceMessage } from '@microsoft/fetch-event-source';
import { nanoid } from 'nanoid';
import { logExecution } from './utils';
import { globalError } from './stores'; // Corrected path
import { uiSessions, knownThreadIds, activeSessionId } from './stores'; // Corrected path
import { addThreadToSession, addKnownThreadId } from './sessionManager'; // Corrected import name

// Types from global.d.ts are globally available.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Core API Fetch Helper (Simplified) ---
async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
    globalError.set(null); // Clear global error at start

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
            } catch (e) { /* Ignore reading body error */ }
            throw new Error(errorMsg);
        }

        if (response.status === 204) { // Handle No Content
            return undefined as T;
        }

        return await response.json() as T;

    } catch (error: unknown) {
        if (!(error instanceof DOMException && error.name === 'AbortError')) {
            console.error('API Fetch Error:', url, error);
            const errorMsg = error instanceof Error ? error.message : String(error);
            globalError.set(errorMsg || 'An unknown API error occurred.');
            throw error; // Re-throw non-abort errors
        } else {
            console.log('API Fetch aborted:', url);
            throw error; // Re-throw AbortError
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
 * Note: Depending on backend implementation, this might be large.
 * Consider if pagination or fetching specific checkpoints is needed later.
 */
export const getFullHistory = (threadId: string, signal?: AbortSignal): Promise<HistoryEntry[]> => {
    return logExecution(`Fetch full history for thread ${threadId}`, () =>
        apiFetch<HistoryEntry[]>(`${BASE_URL}/threads/${threadId}/history`, {}, signal)
    );
};


// --- Stream Run Function ---

interface StreamCallbacks {
    onThreadInfo: (data: SSEThreadInfoData) => void;
    onChunk: (threadId: string, chunk: string, nodeId: string | null) => void;
    onToolChunk: (threadId: string, data: SSEToolCallChunkData, nodeId: string | null) => void;
    onToolResult: (threadId: string, data: SSEToolResultData, nodeId: string | null) => void;
    onError: (threadId: string | null, error: string, nodeId: string | null) => void;
    onEnd: (threadId: string, data: SSEEndData, nodeId: string | null) => void;
    onClose: () => void;
}

/**
 * Initiates a stream run for the active session.
 * Handles sending the request with CheckpointConfigurable and processing SSE events.
 */
export const streamRun = async (
    userInput: string,
    runConfig: RunConfig,
    callbacks: StreamCallbacks
): Promise<AbortController> => {
    globalError.set(null);
    const controller = new AbortController();
    const currentActiveSessionId = get(activeSessionId);

    if (!currentActiveSessionId) {
        const errorMsg = "Cannot start run: No active session selected.";
        console.error(errorMsg);
        globalError.set(errorMsg);
        // Return an already aborted controller
        controller.abort();
        return controller;
    }

    // Get the current session state to determine the target thread_id
    const sessionState = get(uiSessions)[currentActiveSessionId];
    if (!sessionState) {
        const errorMsg = `Cannot start run: Active session state not found for ID ${currentActiveSessionId}.`;
        console.error(errorMsg);
        globalError.set(errorMsg);
        controller.abort();
        return controller;
    }

    // Determine thread_id: null for new, first ID for existing (simplification for now)
    // Determine thread_id: null for new, first ID for existing (simplification for now, per refactor_plan.md)
    const threadIdToSend: string | null = sessionState.threadIds.length > 0 ? sessionState.threadIds[0] : null;

    const checkpointConfigurable: CheckpointConfigurable = {
        thread_id: threadIdToSend,
        runConfig: runConfig,
    };

    // Construct request body according to refactor_plan.md API requirements
    const requestBody = {
        input: { type: 'human', content: userInput }, // Input structure defined in plan
        configurable: checkpointConfigurable,
    };

    logExecution(`Stream run for session ${currentActiveSessionId} (Thread: ${threadIdToSend ?? 'NEW'})`, async () => {
        try {
            await fetchEventSource(`${BASE_URL}/runs/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
                body: JSON.stringify(requestBody),
                signal: controller.signal,
                openWhenHidden: true, // Keep running even if tab is backgrounded

                onopen: async (response) => {
                    if (!response.ok) {
                        let errorMsg = `SSE connection failed! Status: ${response.status}`;
                        try { const errorBody = await response.json(); errorMsg += ` - ${errorBody.detail || JSON.stringify(errorBody)}`; } catch (e) { /* Ignore */ }
                        callbacks.onError(threadIdToSend, `Connection Error: ${errorMsg}`, null);
                        throw new Error(errorMsg); // Throw to abort fetchEventSource
                    }
                    console.log(`SSE stream opened for session ${currentActiveSessionId}`);
                },

                onmessage: (event: EventSourceMessage) => {
                    try {
                        if (!event.data) { console.warn('SSE message received with no data.'); return; }
                        const parsedEvent: SSEEventData = JSON.parse(event.data);
                        const eventType = parsedEvent.type;
                        const eventData = parsedEvent.data;
                        const eventNodeId = parsedEvent.node ?? null;
                        // CRITICAL: Backend MUST send thread_id in events for routing (per refactor_plan.md)
                        const eventThreadId = parsedEvent.thread_id;

                        if (!eventThreadId && eventType !== 'error' && eventType !== 'thread_info') {
                             // thread_info is special, it provides the ID for a new thread
                             console.error(`SSE event type '${eventType}' received without thread_id. Cannot route reliably.`, parsedEvent);
                             callbacks.onError(threadIdToSend, `System Error: Received event type '${eventType}' without required thread_id.`, eventNodeId);
                             return; // Cannot process reliably
                        }

                        // Use the thread_id from the event if available, otherwise use the one we sent (for new threads before thread_info)
                        const targetThreadId = eventThreadId || threadIdToSend;

                        // Route based on event type
                        switch (eventType) {
                            case 'thread_info': // Event carrying the new thread_id
                                const threadInfo = eventData as SSEThreadInfoData;
                                if (threadInfo.thread_id && threadIdToSend === null) {
                                    // This is the confirmation for a newly created thread
                                    console.log(`Received new thread ID: ${threadInfo.thread_id} for session ${currentActiveSessionId}`);
                                    // Update frontend state via sessionManager
                                    addKnownThreadId(threadInfo.thread_id); // Use corrected function name
                                    addThreadToSession(currentActiveSessionId, threadInfo.thread_id);
                                    callbacks.onThreadInfo(threadInfo);
                                } else if (threadInfo.thread_id && threadInfo.thread_id !== threadIdToSend) {
                                     // This shouldn't happen if backend logic is correct
                                     console.warn(`Received thread_info with ID ${threadInfo.thread_id} that doesn't match expected target ${threadIdToSend}`);
                                } else if (!threadInfo.thread_id) {
                                     console.error(`Received 'thread_info' event without a thread_id.`, eventData);
                                     callbacks.onError(threadIdToSend, "System Error: Invalid 'thread_info' received.", eventNodeId);
                                }
                                break;
                            case 'chunk':
                                // Ensure targetThreadId is valid before calling callback
                                if (targetThreadId) {
                                    callbacks.onChunk(targetThreadId, eventData as string, eventNodeId);
                                } else {
                                     console.error(`Cannot process 'chunk' without targetThreadId.`, parsedEvent);
                                     callbacks.onError(null, "System Error: Cannot process 'chunk' without thread ID.", eventNodeId);
                                }
                                break;
                            case 'ai_tool_chunk':
                                if (targetThreadId) {
                                    callbacks.onToolChunk(targetThreadId, eventData as SSEToolCallChunkData, eventNodeId);
                                } else {
                                     console.error(`Cannot process 'ai_tool_chunk' without targetThreadId.`, parsedEvent);
                                     callbacks.onError(null, "System Error: Cannot process 'ai_tool_chunk' without thread ID.", eventNodeId);
                                }
                                break;
                            case 'tool_result':
                                if (targetThreadId) {
                                    callbacks.onToolResult(targetThreadId, eventData as SSEToolResultData, eventNodeId);
                                } else {
                                     console.error(`Cannot process 'tool_result' without targetThreadId.`, parsedEvent);
                                     callbacks.onError(null, "System Error: Cannot process 'tool_result' without thread ID.", eventNodeId);
                                }
                                break;
                            case 'error':
                                // Error event might not have thread_id if it's a general graph error
                                // Ensure eventData is treated as a string for the callback
                                const errorString = typeof eventData === 'string' ? eventData : JSON.stringify(eventData);
                                callbacks.onError(targetThreadId, errorString, eventNodeId);
                                break;
                            case 'end':
                                if (targetThreadId) {
                                    callbacks.onEnd(targetThreadId, eventData as SSEEndData, eventNodeId);
                                } else {
                                     console.error(`Cannot process 'end' without targetThreadId.`, parsedEvent);
                                     callbacks.onError(null, "System Error: Cannot process 'end' without thread ID.", eventNodeId);
                                }
                                break;
                            default:
                                console.warn('Unhandled SSE event type:', eventType, parsedEvent);
                        }
                    } catch (error: unknown) {
                        console.error('Failed to parse or handle SSE message data:', event.data, error);
                        // Ensure error message passed to callback is a string
                        const errorMsg = error instanceof Error ? error.message : String(error);
                        callbacks.onError(threadIdToSend, `Failed to process message: ${errorMsg}`, null);
                    }
                },

                onclose: () => {
                    console.log(`SSE stream closed for session ${currentActiveSessionId}`);
                    callbacks.onClose(); // Notify caller
                },

                onerror: (err) => {
                    if (controller.signal.aborted) { return; } // Don't treat abort as error
                    console.error(`SSE stream error for session ${currentActiveSessionId}:`, err);
                    const errorMsg = err instanceof Error ? err.message : String(err);
                    callbacks.onError(threadIdToSend, `Stream Error: ${errorMsg}`, null);
                    // Don't throw from onerror, allow graceful closure. Error state is set via callback.
                    // fetchEventSource will stop retrying on fatal errors automatically.
                },
            });
        } catch (error) {
            // Catches errors from fetchEventSource setup (e.g., network error before connection)
            // or the explicit throw in onopen.
            if (!(error instanceof DOMException && error.name === 'AbortError')) {
                console.error(`Error setting up SSE stream for session ${currentActiveSessionId}:`, error);
                callbacks.onError(threadIdToSend, `Stream Setup Error: ${error instanceof Error ? error.message : String(error)}`, null);
            }
            // Don't re-throw here, logExecution handles logging the failure based on the caught error.
        }
    }); // End logExecution wrapper

    return controller; // Return controller so the caller can abort
};

// --- Removed Old Functions ---
// fetchConstitutions, fetchHistory, submitConstitution, fetchConstitutionContent,
// streamCompareRun (marked TODO), deleteThread, and all old SSE helpers removed.

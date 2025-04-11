import { persistedLocalState } from './utils/persistedLocalState.svelte';


/**
 * List of all LangGraph thread IDs known to this client. Acts as an index.
 * Synced with localStorage key 'superego_knownThreads'.
 */
export const persistedKnownThreadIds = persistedLocalState<string[]>('superego_knownThreads', []); // Renamed variable

/**
 * Holds state for ALL UI sessions/tabs, keyed by sessionId.
 * Maps UI tabs to backend thread IDs.
 * Synced with localStorage key 'superego_uiSessions'.
 */
export const persistedUiSessions = persistedLocalState<Record<string, UISessionState>>('superego_uiSessions', {}); // Renamed variable

/**
 * Tracks the sessionId of the currently viewed session/tab
 */
export const persistedActiveSessionId = persistedLocalState<string | null>('superego_activeSessionId', null); // Renamed variable

/**
 * Central cache holding the latest known state and status for each thread.
 * Keyed by threadId. NOT persisted.
 */
export let threadCacheStore = $state<Record<string, ThreadCacheData>>({});

// Function to update the thread cache state immutably
export function updateThreadCache(updater: (currentCache: Record<string, ThreadCacheData>) => Record<string, ThreadCacheData>) {
	threadCacheStore = updater(threadCacheStore);
}

// Specific helper to update or add a single entry
export function setThreadCacheEntry(threadId: string, entryData: ThreadCacheData) {
    threadCacheStore = { ...threadCacheStore, [threadId]: entryData };
}

// Specific helper to update properties of an existing entry
export function updateThreadCacheEntry(threadId: string, updates: Partial<ThreadCacheData>) {
    if (threadCacheStore[threadId]) {
        threadCacheStore[threadId] = { ...threadCacheStore[threadId], ...updates };
    } else {
        console.warn(`[stores] Attempted to update non-existent thread cache entry: ${threadId}`);
    }
}

/** Store for displaying global errors */
export let globalError = $state<string | null>(null);

export function setGlobalError(error: string | null) {
	globalError = error;
}
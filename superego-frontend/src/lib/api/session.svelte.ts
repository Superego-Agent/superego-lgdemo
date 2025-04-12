import { logExecution } from '$lib/utils'; // Correct path for utils barrel file
import { activeStore } from '$lib/state/active.svelte'; // Use new active store

// Base URL for the API - Consider moving to a shared config if used elsewhere
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// Generic API fetch function - Consider moving to a shared utility if needed by other API modules
async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
    activeStore.clearGlobalError();

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
            activeStore.setGlobalError(errorMsg || 'An unknown API error occurred.');
            throw error;
        } else {
            console.log('API Fetch aborted:', url);
            throw error;
        }
    }
}


/**
 * Fetches all relevant history entries for a given thread.
 */
export const getFullHistory = (threadId: string, signal?: AbortSignal): Promise<HistoryEntry[]> => {
    return logExecution(`Fetch full history for thread ${threadId}`, () =>
        apiFetch<HistoryEntry[]>(`${BASE_URL}/threads/${threadId}/history`, {}, signal)
    );
};

/**
 * Fetches the latest history entry (state) for a given thread.
 */
export const getLatestHistory = (threadId: string, signal?: AbortSignal): Promise<HistoryEntry> => {
    return logExecution(`Fetch latest history for thread ${threadId}`, () =>
        apiFetch<HistoryEntry>(`${BASE_URL}/threads/${threadId}/latest`, {}, signal)
    );
};
import { get } from 'svelte/store';
import { logExecution } from './utils';
import { globalError } from './stores.svelte'; // Removed threadCacheStore
import { persistedUiSessions, persistedKnownThreadIds, persistedActiveSessionId, setGlobalError } from './stores.svelte';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
    setGlobalError(null);

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
            setGlobalError(errorMsg || 'An unknown API error occurred.');
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
        setGlobalError(null);
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
                setGlobalError(errorMsg || 'An unknown API error occurred fetching constitution content.');
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

/**
 * Fetches the latest history entry (state) for a given thread.
 */
export const getLatestHistory = (threadId: string, signal?: AbortSignal): Promise<HistoryEntry> => {
    return logExecution(`Fetch latest history for thread ${threadId}`, () =>
        apiFetch<HistoryEntry>(`${BASE_URL}/threads/${threadId}/latest`, {}, signal)
    );
};

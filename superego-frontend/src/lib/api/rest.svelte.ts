import { logExecution } from '../utils'; 
import { activeStore } from '$lib/state/active.svelte'; // Use new active store

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

// --- Core API Fetch Helper ---

/**
 * Generic fetch wrapper for API calls, handling errors and JSON parsing.
 * Sets global error state via appState.
 */
async function apiFetch<T>(url: string, options: RequestInit = {}, signal?: AbortSignal): Promise<T> {
	activeStore.clearGlobalError(); // Use method

	try {
		const response = await fetch(url, {
			...options,
			signal,
			headers: {
				'Content-Type': 'application/json',
				'Accept': 'application/json',
				...options.headers
			}
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
			} catch (e) {
				/* Ignore */
			}
			throw new Error(errorMsg);
		}

		if (response.status === 204) {
			// Handle No Content response
			return undefined as T;
		}

		// Assume JSON response otherwise
		return (await response.json()) as T;
	} catch (error: unknown) {
		if (!(error instanceof DOMException && error.name === 'AbortError')) {
			console.error('API Fetch Error:', url, error);
			const errorMsg = error instanceof Error ? error.message : String(error);
			activeStore.setGlobalError(errorMsg || 'An unknown API error occurred.'); // Use method
			throw error; // Re-throw after setting global state
		} else {
			console.log('API Fetch aborted:', url);
			throw error; // Re-throw abort error
		}
	}
}


// --- Constitution API Functions ---

/**
 * Fetches the list of available global constitutions.
 */
export const fetchAvailableConstitutions = (signal?: AbortSignal): Promise<ConstitutionItem[]> => {
	return logExecution('Fetch available constitutions', () =>
		apiFetch<ConstitutionItem[]>(`${BASE_URL}/constitutions`, {}, signal)
	);
};

/**
 * Fetches the full text content of a specific global constitution.
 * Uses raw fetch as the endpoint returns plain text, not JSON.
 */
export const fetchConstitutionContent = (constitutionId: string, signal?: AbortSignal): Promise<string> => {
	return logExecution(`Fetch content for constitution ${constitutionId}`, async () => {
		activeStore.clearGlobalError(); // Use method
		try {
			const response = await fetch(`${BASE_URL}/constitutions/${constitutionId}/content`, {
				signal,
				headers: { Accept: 'text/plain' } // Request plain text
			});
			if (!response.ok) {
				let errorMsg = `HTTP error! Status: ${response.status}`;
				try {
					const errorText = await response.text();
					errorMsg += ` - ${errorText}`;
				} catch (e) {
					/* Ignore */
				}
				throw new Error(errorMsg);
			}
			return await response.text();
		} catch (error: unknown) {
			if (!(error instanceof DOMException && error.name === 'AbortError')) {
				console.error(`API Fetch Error (Text): ${BASE_URL}/constitutions/${constitutionId}/content`, error);
				const errorMsg = error instanceof Error ? error.message : String(error);
				activeStore.setGlobalError(errorMsg || 'An unknown API error occurred fetching constitution content.'); // Use method
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
 */
export const submitConstitution = (
	payload: ConstitutionSubmission,
	signal?: AbortSignal
): Promise<SubmissionResponse> => {
	return logExecution('Submit constitution for review', () =>
		apiFetch<SubmissionResponse>(
			`${BASE_URL}/constitutions`,
			{
				method: 'POST',
				body: JSON.stringify(payload)
			},
			signal
		)
	);
};
import { logExecution } from '../utils/utils';
import { activeStore } from '$lib/state/active.svelte';
import { getEncryptedApiKey } from '$lib/state/apiKey.svelte';
import { getOrCreateSessionId } from '$lib/utils/crypto';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

/**
 * Sends the encrypted API key to the backend server
 * @returns A promise that resolves to a success message or rejects with an error
 */
export async function sendApiKeyToBackend(): Promise<{ status: string; message: string }> {
  return logExecution('Send API key to backend', async () => {
    activeStore.clearGlobalError();
    
    // Get the encrypted API key and session ID
    const encryptedApiKey = getEncryptedApiKey();
    const sessionId = getOrCreateSessionId();
    console.log('[apiKey.svelte.ts] Sending API key to backend, encrypted key length:', encryptedApiKey ? encryptedApiKey.length : 0);
    console.log('[apiKey.svelte.ts] Using session ID:', sessionId);
    
    try {
      // Make sure we're using the correct field names expected by the backend
      console.log('[apiKey.svelte.ts] Request body fields: encrypted_key, session_id');
      const requestBody = JSON.stringify({ 
        encrypted_key: encryptedApiKey,
        session_id: sessionId
      });
      console.log('[apiKey.svelte.ts] Request body:', requestBody);
      
      const response = await fetch(`${BASE_URL}/key/set`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: requestBody,
      });
      
      // Always parse the response, even if it's not "ok"
      const result = await response.json();
      
      // Check if the response indicates we need an API key
      if (result.status === "needs_key") {
        activeStore.setGlobalError(result.message || "Please enter your API key");
        throw new Error(result.message || "API key is required");
      }
      
      // Store the session ID from the response if provided
      if (result.session_id) {
        console.log('[apiKey.svelte.ts] Received session ID from server:', result.session_id);
        // We don't need to store it since we're using localStorage in getOrCreateSessionId
      }
      
      // Check for other error responses
      if (!response.ok) {
        let errorMsg = `HTTP error! Status: ${response.status}`;
        if (result.detail || result.message) {
          errorMsg += ` - ${result.detail || result.message}`;
        }
        activeStore.setGlobalError(errorMsg);
        throw new Error(errorMsg);
      }
      
      return result;
    } catch (error) {
      console.error('Error sending API key to backend:', error);
      const errorMsg = error instanceof Error ? error.message : String(error);
      activeStore.setGlobalError(errorMsg || 'An unknown error occurred while sending API key');
      throw error;
    }
  });
}

import { writable } from 'svelte/store';
import { encryptApiKey } from '../utils/crypto';

// Create a writable store for the API key that is not persisted
export const apiKeyStore = writable<string>('');

// Create a derived store for the encrypted API key
export const encryptedApiKeyStore = writable<string>('');

// Helper functions to work with the API key
export function setApiKey(key: string): void {
  console.log('[apiKey.svelte.ts] Setting API key, length:', key ? key.length : 0);
  apiKeyStore.set(key);
  
  // When the API key is set, also update the encrypted version
  if (key) {
    const encrypted = encryptApiKey(key);
    console.log('[apiKey.svelte.ts] Encrypted API key, length:', encrypted ? encrypted.length : 0);
    encryptedApiKeyStore.set(encrypted);
  } else {
    console.log('[apiKey.svelte.ts] Clearing encrypted API key');
    encryptedApiKeyStore.set('');
  }
}

export function clearApiKey(): void {
  apiKeyStore.set('');
  encryptedApiKeyStore.set('');
}

// Export a derived store that just indicates if an API key is set
export function hasApiKey(): boolean {
  let hasKey = false;
  apiKeyStore.subscribe(key => {
    hasKey = key.trim().length > 0;
  })();
  return hasKey;
}

// Get the current encrypted API key value
export function getEncryptedApiKey(): string {
  let encryptedKey = '';
  encryptedApiKeyStore.subscribe(key => {
    encryptedKey = key;
  })();
  console.log('[apiKey.svelte.ts] Getting encrypted API key, length:', encryptedKey ? encryptedKey.length : 0);
  return encryptedKey;
}

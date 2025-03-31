// src/lib/stores.ts
import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';

// --- Core Chat State ---
/** List of messages currently displayed in the chat interface. */
export const messages: Writable<MessageType[]> = writable([]);

/** The ID of the currently active chat thread. Null if it's a new chat. */
export const currentThreadId: Writable<string | null> = writable(null);

/** Flag indicating if the backend is currently processing a request. */
export const isLoading: Writable<boolean> = writable(false);

// --- Application Mode ---
/** The current operational mode ('chat', 'use' constitution, 'compare' constitutions). */
export const currentMode: Writable<AppMode> = writable('chat');

// --- Constitution State ---
/** List of all constitutions fetched from the backend. */
export const availableConstitutions: Writable<ConstitutionItem[]> = writable([]);

/** List of constitution IDs currently selected/active in 'use' mode. */
export const activeConstitutionIds: Writable<string[]> = writable(['none']); // Default to 'none'

// --- Compare Mode State ---
/** List of constitution sets defined for comparison. */
export const compareSets: Writable<CompareSet[]> = writable([]);

// --- Thread Management State ---
/** List of existing chat threads fetched from the backend. */
export const availableThreads: Writable<ThreadItem[]> = writable([]);

// --- Potentially add error store ---
/** Store for displaying global errors */
export const globalError: Writable<string | null> = writable(null);
// src/lib/stores.ts
import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';

// --- Core Chat State ---
/** List of messages currently displayed in the chat interface. */
export const messages: Writable<MessageType[]> = writable([]);

/**
 * The ID of the currently active chat thread (from the metadata database).
 * Null if it's a new chat that hasn't had its first run yet.
 */
export const currentThreadId: Writable<number | null> = writable(null);

/** Flag indicating if the backend is currently processing a request. */
export const isLoading: Writable<boolean> = writable(false);

// --- Application Mode ---
/** The current operational mode ('chat', 'use' constitution, 'compare' constitutions). */
export const currentMode: Writable<AppMode> = writable('chat');

// --- Constitution State ---
/** List of all constitutions fetched from the backend. */
export const availableConstitutions: Writable<ConstitutionItem[]> = writable([]);

/** List of constitution IDs currently selected/active for the next run. */
export const activeConstitutionIds: Writable<string[]> = writable(['none']); // Default to 'none'

// --- Compare Mode State ---
/** List of constitution sets defined for comparison. */
export const compareSets: Writable<CompareSet[]> = writable([]);

// --- Thread Management State ---
/** List of existing chat threads fetched from the backend metadata DB. */
export const availableThreads: Writable<ThreadItem[]> = writable([]);

// --- Error Store ---
/** Store for displaying global errors */
export const globalError: Writable<string | null> = writable(null);

// --- Helper function to reset state for a new chat ---
export function resetForNewChat() {
    messages.set([]);
    currentThreadId.set(null);
    // Optionally reset active constitutions or other relevant state
    // activeConstitutionIds.set(['none']);
    globalError.set(null);
    // Keep availableConstitutions and availableThreads loaded
}
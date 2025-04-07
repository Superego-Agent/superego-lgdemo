// src/lib/stores.ts
import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';
import { createNewConversation, findConversationById } from './conversationManager'; // Import necessary functions
import type { ConversationMetadata } from './conversationManager'; // Import the type

// TODO: Define or import these types if not already done elsewhere
type MessageType = any;
type AppMode = 'chat' | 'use' | 'compare';
// Updated to match backend API response after Phase 1 changes
type ConstitutionItem = { id: string; title: string; description?: string };
type CompareSet = any;
// type ThreadItem = any; // Assuming this was implicitly used or defined elsewhere

// --- Core Chat State ---
/** List of messages currently displayed in the chat interface. */
export const messages: Writable<MessageType[]> = writable([]);

/**
 * The client-side ID (`ConversationMetadata.id`) of the currently selected conversation.
 * Null if no conversation is selected (e.g., initial state).
 */
export const activeConversationId: Writable<string | null> = writable(null);

/**
 * The backend thread_id (UUID string) of the currently active conversation.
 * Derived from the activeConversationId and managedConversations.
 * Null if the active conversation is new or hasn't interacted with the backend yet.
 */
export const activeThreadId: Writable<string | null> = writable(null);

// Subscribe to activeConversationId to update activeThreadId
activeConversationId.subscribe(id => {
    if (id) {
        const conversation = findConversationById(id);
        activeThreadId.set(conversation?.thread_id ?? null);
    } else {
        activeThreadId.set(null);
    }
});


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
// NOTE: This store might be refactored or its usage changed once ConstitutionSelector uses adherence levels as the primary state.

/** Stores the adherence level (1-5) for each active constitution. Maps constitution ID to level. */
export const constitutionAdherenceLevels: Writable<Record<string, number>> = writable({});

// --- Compare Mode State ---
/** List of constitution sets defined for comparison. */
export const compareSets: Writable<CompareSet[]> = writable([]);

// --- Thread Management State ---
// availableThreads is now replaced by managedConversations in conversationManager.ts

// --- Error Store ---
/** Store for displaying global errors */
export const globalError: Writable<string | null> = writable(null);

// --- Helper function to reset state for a new chat ---
export function resetForNewChat() {
    messages.set([]);
    const newConversation = createNewConversation(); // Create new entry in localStorage
    activeConversationId.set(newConversation.id); // Set the new one as active
    // activeThreadId will be updated automatically by its subscription
    activeConstitutionIds.set(['none']); // Reset selected IDs (legacy, might be removed later)
    constitutionAdherenceLevels.set({}); // Reset adherence levels for the new chat
    globalError.set(null);
    // Keep availableConstitutions loaded
}

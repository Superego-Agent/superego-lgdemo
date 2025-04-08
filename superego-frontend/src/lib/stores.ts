// src/lib/stores.ts
import { writable, get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import { createNewConversation, managedConversations } from './conversationManager';
import type { ConversationMetadata } from './conversationManager';
import { fetchHistory } from './api';
import { logExecution } from './utils';

// --- Stores ---

/** Holds the state for all known conversations, keyed by client-side ID. */
export const conversationStates: Writable<Record<string, ConversationState>> = writable({});

/**
 * The client-side ID (`ConversationMetadata.id`) of the currently selected conversation.
 * Null if no conversation is selected.
 */
export const activeConversationId: Writable<string | null> = writable(null);

/** Store for displaying global errors (e.g., API connection failures). */
export const globalError: Writable<string | null> = writable(null);

/** The current operational mode ('chat', 'use', 'compare'). */
// TODO: Review if mode should derive from activeConversationId/type instead.
export const currentMode: Writable<AppMode> = writable('chat');

/** List of all constitutions fetched from the backend. */
// TODO: Consider if constitutions/levels should be part of ConversationState if they can differ per run.
export const availableConstitutions: Writable<ConstitutionItem[]> = writable([]);

/** List of constitution IDs currently selected for the next run. */
export const activeConstitutionIds: Writable<string[]> = writable(['none']);

/** Adherence level (1-5) for each active constitution (maps constitution ID -> level). */
export const constitutionAdherenceLevels: Writable<Record<string, number>> = writable({});

/** List of constitution sets defined for comparison mode. */
// TODO: Integrate compareSets with the ConversationState model (e.g., type: 'compare_session').
export const compareSets: Writable<CompareSet[]> = writable([]);


// --- Initialization ---
// Initialize conversationStates from localStorage metadata.
function initializeStates() {
    const initialMetadata = get(managedConversations);
    const initialStates: Record<string, ConversationState> = {};
    initialMetadata.forEach(meta => {
        initialStates[meta.id] = {
            metadata: meta,
            messages: [],
            status: 'idle',
            error: undefined,
            abortController: undefined
        };
    });
    conversationStates.set(initialStates);
}
initializeStates();

// --- Central Subscription Logic ---
// Handles aborting previous requests and triggering history fetch for the new active conversation.
let previousActiveId: string | null = null;

activeConversationId.subscribe(async (activeId) => {
    const currentStates = get(conversationStates);

    // Abort previous fetch if ongoing and switching away
    if (previousActiveId && previousActiveId !== activeId) {
        const previousState = currentStates[previousActiveId];
        if (previousState?.abortController) {
            previousState.abortController.abort();
            // State update (clearing controller, setting status) is handled within fetchHistory's finally block
        }
    }

    if (activeId) {
        const activeState = currentStates[activeId];

        // Load history if state exists, is idle, has no messages, and has a backend thread_id
        if (activeState && activeState.status === 'idle' && activeState.messages.length === 0 && activeState.metadata.thread_id) {
            const controller = new AbortController();
            // Update state immediately to 'loading_history' and store controller
            conversationStates.update(s => {
                if (s[activeId]) {
                    s[activeId].status = 'loading_history';
                    s[activeId].error = undefined;
                    s[activeId].abortController = controller;
                }
                return s;
            });

            // Use logExecution to wrap the fetchHistory call
            try {
                await logExecution(`Fetch history for ${activeId}`, () =>
                    fetchHistory(activeState.metadata.thread_id!, controller.signal, activeId)
                );
            } catch (error) {
                // logExecution already logs the error. We only need to handle non-abort errors
                // for specific state updates here if fetchHistory didn't handle it.
                const errorIsAbort = error instanceof DOMException && error.name === 'AbortError';
                if (!errorIsAbort) {
                    // Ensure state is updated to 'error' if fetchHistory failed unexpectedly
                    // and didn't clean up itself (e.g., via its finally block).
                    conversationStates.update(s => {
                        if (s[activeId] && s[activeId].status === 'loading_history') { // Avoid overwriting later states
                            s[activeId].status = 'error';
                            s[activeId].error = error instanceof Error ? error.message : String(error);
                            s[activeId].abortController = undefined; // Clear controller on unexpected error
                        }
                        return s;
                    });
                }
                // If it's an AbortError, we assume fetchHistory's finally block handled state updates.
            }
        }
    }

    previousActiveId = activeId;
});


// --- Helper Functions ---

/** Utility to update parts of a specific conversation's state. */
export function updateConversationState(clientId: string, updates: Partial<Omit<ConversationState, 'metadata'>>) {
     conversationStates.update(s => {
         if (s[clientId]) {
             s[clientId] = { ...s[clientId], ...updates };
         }
         return s;
     });
}

/** Utility to update metadata within a specific conversation's state (e.g., after rename). */
export function updateConversationMetadataState(clientId: string, metadataUpdates: Partial<Omit<ConversationMetadata, 'id'>>) {
    conversationStates.update(s => {
        if (s[clientId]) {
            s[clientId].metadata = { ...s[clientId].metadata, ...metadataUpdates };
         }
         return s;
     });
}

/** Ensures a state entry exists for a given conversation metadata, creating a default one if needed. */
export function ensureConversationStateExists(conversation: ConversationMetadata) {
    conversationStates.update(s => {
        if (!s[conversation.id]) {
            s[conversation.id] = {
                metadata: conversation,
                messages: [],
                status: 'idle',
                error: undefined,
                abortController: undefined
            };
         }
         return s;
     });
}

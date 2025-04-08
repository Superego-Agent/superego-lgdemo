// src/lib/stores.ts
import { writable, get } from 'svelte/store'; // Import get
import type { Writable } from 'svelte/store';
import { createNewConversation, managedConversations } from './conversationManager'; // Import necessary functions and the conversations store
import type { ConversationMetadata } from './conversationManager'; // Import the type
import { fetchHistory } from './api'; // Import fetchHistory for the subscription logic

// Types MessageType, AppMode, ConstitutionItem, CompareSet are defined globally in src/global.d.ts

// --- Conversation-Centric State ---

export interface ConversationState {
    metadata: ConversationMetadata; // From conversationManager
    messages: MessageType[];
    status: 'idle' | 'loading_history' | 'streaming' | 'error'; // Granular status
    error?: string; // Error specific to this conversation
    abortController?: AbortController; // Controller for ongoing fetch/stream
}

/**
 * Holds the state for all known conversations, keyed by their client-side ID.
 */
export const conversationStates: Writable<Record<string, ConversationState>> = writable({});

/**
 * The client-side ID (`ConversationMetadata.id`) of the currently selected conversation.
 * Null if no conversation is selected (e.g., initial state or new chat).
 */
export const activeConversationId: Writable<string | null> = writable(null);

// --- Global Error Store ---
/** Store for displaying global errors (e.g., API connection failures) */
export const globalError: Writable<string | null> = writable(null);


// --- Application Mode ---
/** The current operational mode ('chat', 'use' constitution, 'compare' constitutions). */
// TODO: Review if this is still the best way to manage mode or if it should derive from activeConversationId/type
export const currentMode: Writable<AppMode> = writable('chat'); // Keep for now, might refactor later

// --- Constitution State ---
/** List of all constitutions fetched from the backend. */
// TODO: Consider if these should be part of ConversationState if they can differ per conversation run
export const availableConstitutions: Writable<ConstitutionItem[]> = writable([]);

/** List of constitution IDs currently selected/active for the next run. */
export const activeConstitutionIds: Writable<string[]> = writable(['none']); // Default to 'none'

/** Stores the adherence level (1-5) for each active constitution. Maps constitution ID to level. */
export const constitutionAdherenceLevels: Writable<Record<string, number>> = writable({});

// --- Compare Mode State ---
/** List of constitution sets defined for comparison. */
// TODO: Integrate this with the ConversationState model (e.g., type: 'compare_session')
export const compareSets: Writable<CompareSet[]> = writable([]);


// --- Initialization Logic ---
// Initialize conversationStates from managedConversations (localStorage)
function initializeStates() {
    const initialMetadata = get(managedConversations);
    const initialStates: Record<string, ConversationState> = {};
    initialMetadata.forEach(meta => {
        initialStates[meta.id] = {
            metadata: meta,
            messages: [], // Start empty, load on demand
            status: 'idle',
            error: undefined,
            abortController: undefined
        };
    });
    conversationStates.set(initialStates);
    console.log("Initialized conversationStates from localStorage metadata.");

    // Optionally set the first conversation as active on initial load?
    // if (initialMetadata.length > 0) {
    //     activeConversationId.set(initialMetadata[0].id);
    // }
}
initializeStates(); // Run initialization

// Keep managedConversations subscription to update conversationStates if metadata changes externally (e.g., rename)
// Or handle metadata updates directly within conversationStates updates? Simpler to handle directly.
// Let's assume updates to metadata (like name) are pushed via updateConversationState function below.

// --- Central Subscription Logic ---
let previousActiveId: string | null = null;

activeConversationId.subscribe(async (activeId) => {
    console.log(`Store subscriber: activeConversationId changed from ${previousActiveId} to ${activeId}`);

    const currentStates = get(conversationStates);

    // Abort previous fetch if ongoing and it wasn't for the *new* activeId
    if (previousActiveId && previousActiveId !== activeId) {
        const previousState = currentStates[previousActiveId];
        if (previousState?.abortController) {
            console.log(`Store subscriber: Aborting request for previously active conversation ${previousActiveId}`);
            previousState.abortController.abort();
            // Update state to reflect abortion? Or let finally block in fetchHistory handle it?
            // Let finally handle it for now.
        }
    }

    if (activeId) {
        const activeState = currentStates[activeId];

        // Check if we need to load history (state exists, is idle, has no messages, and has a backend thread_id)
        if (activeState && activeState.status === 'idle' && activeState.messages.length === 0 && activeState.metadata.thread_id) {
            console.log(`Store subscriber: Triggering history fetch for active conversation ${activeId} (Thread ID: ${activeState.metadata.thread_id})`);

            const controller = new AbortController();
            // Update state immediately to 'loading_history' and store controller
            conversationStates.update(s => {
                if (s[activeId]) {
                    s[activeId].status = 'loading_history';
                    s[activeId].error = undefined; // Clear previous error
                    s[activeId].abortController = controller;
                }
                return s;
            });

            try {
                // Call fetchHistory - it should update the state internally via clientId
                // Pass activeId as the clientId
                await fetchHistory(activeState.metadata.thread_id, controller.signal, activeId);
                console.log(`Store subscriber: fetchHistory call completed or aborted for ${activeId}`);
            } catch (error: unknown) { // Type the error as unknown
                // fetchHistory should handle setting error state, but log here just in case
                 const errorIsAbort = error instanceof DOMException && error.name === 'AbortError';
                 if (!errorIsAbort) {
                    console.error(`Store subscriber: Error during fetchHistory call for ${activeId}:`, error);
                    // Ensure state is updated if fetchHistory failed to do so
                    conversationStates.update(s => {
                        if (s[activeId] && s[activeId].status === 'loading_history') { // Check status hasn't changed
                            s[activeId].status = 'error';
                            // Extract message safely
                            s[activeId].error = error instanceof Error ? error.message : String(error);
                            s[activeId].abortController = undefined; // Clear controller on error
                        }
                        return s;
                    });
                 } else {
                     console.log(`Store subscriber: History fetch explicitly aborted for ${activeId}.`);
                     // State should be updated by finally block in fetchHistory (which should also clear controller)
                 }
            }
        } else if (activeState && activeState.status === 'idle' && activeState.messages.length > 0) {
             console.log(`Store subscriber: Conversation ${activeId} already has messages, not fetching history.`);
        } else if (activeState && (activeState.status === 'loading_history' || activeState.status === 'streaming')) {
             console.log(`Store subscriber: Conversation ${activeId} is already loading or streaming.`);
        } else if (!activeState) {
            console.warn(`Store subscriber: Active conversation ${activeId} not found in conversationStates. This might happen briefly during creation.`);
            // If a conversation is created and immediately set active, its state might not exist yet.
            // The creation process (e.g., in api.ts _handleThreadCreated) should initialize its state.
        } else if (activeState && !activeState.metadata.thread_id) {
             console.log(`Store subscriber: Conversation ${activeId} has no backend thread_id, cannot fetch history.`);
        }
    } else {
        console.log("Store subscriber: No active conversation.");
        // No action needed here, UI will react to null activeId
    }

    previousActiveId = activeId; // Update tracker
});


// --- Helper function to update conversation state (e.g., after API calls) ---
// It's often better if the API functions update the state directly using the clientId
// But this can be a utility if needed elsewhere.
export function updateConversationState(clientId: string, updates: Partial<Omit<ConversationState, 'metadata'>>) {
     conversationStates.update(s => {
         if (s[clientId]) {
             s[clientId] = { ...s[clientId], ...updates };
         } else {
             console.warn(`Attempted to update state for non-existent client ID: ${clientId}`);
         }
         return s;
     });
}

// Helper to update metadata within the state (e.g., after rename)
export function updateConversationMetadataState(clientId: string, metadataUpdates: Partial<Omit<ConversationMetadata, 'id'>>) {
    conversationStates.update(s => {
        if (s[clientId]) {
            s[clientId].metadata = { ...s[clientId].metadata, ...metadataUpdates };
        } else {
            console.warn(`Attempted to update metadata state for non-existent client ID: ${clientId}`);
        }
        return s;
    });
}


// --- Helper function to reset state for a new chat ---
// This is now primarily handled by Sidebar setting activeId to null,
// and api.ts initializing state upon thread_created.
// We might need a function to ensure state exists if creating locally *before* backend interaction.
export function ensureConversationStateExists(conversation: ConversationMetadata) {
    conversationStates.update(s => {
        if (!s[conversation.id]) {
            console.log(`Ensuring state exists for new/loaded conversation ${conversation.id}`);
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

// Example Usage after creating a conversation locally:
// const newConv = createNewConversation();
// ensureConversationStateExists(newConv);
// activeConversationId.set(newConv.id);

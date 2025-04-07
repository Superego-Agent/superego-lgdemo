// src/lib/conversationManager.ts

import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';
import { v4 as uuidv4 } from 'uuid'; // Need to install uuid: npm install uuid @types/uuid

const LOCAL_STORAGE_KEY = 'superego_conversations';

// --- Interface for Conversation Metadata ---
export interface ConversationMetadata {
	/** Unique ID for this entry in localStorage (client-side) */
	id: string;
	/** User-defined name for the conversation */
	name: string;
	/** Backend thread_id (UUID string) associated with this conversation */
	thread_id: string | null; // Can be null initially until first backend interaction
	/** ISO timestamp string for creation date */
	created_at: string;
	/** ISO timestamp string for last update */
	last_updated_at: string;
	/** IDs of constitutions used in the most recent run of this thread */
	last_used_constitution_ids: string[];
    /** Optional preview text */
    preview?: string;
}

// --- Helper Functions ---

/** Loads all conversation metadata from localStorage */
function loadConversationsFromStorage(): ConversationMetadata[] {
	try {
		const storedData = localStorage.getItem(LOCAL_STORAGE_KEY);
		if (storedData) {
			const parsedData = JSON.parse(storedData);
            // Basic validation (can be improved)
            if (Array.isArray(parsedData)) {
                // Sort by last updated date, newest first
                return parsedData.sort((a, b) =>
                    new Date(b.last_updated_at).getTime() - new Date(a.last_updated_at).getTime()
                );
            }
		}
	} catch (error) {
		console.error("Error loading conversations from localStorage:", error);
		// Optionally clear corrupted data: localStorage.removeItem(LOCAL_STORAGE_KEY);
	}
	return [];
}

/** Saves the entire list of conversations to localStorage */
function saveConversationsToStorage(conversations: ConversationMetadata[]) {
	try {
		localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(conversations));
	} catch (error) {
		console.error("Error saving conversations to localStorage:", error);
        // Handle potential storage full errors etc.
	}
}

// --- Svelte Store ---

/** Writable store holding the list of managed conversations */
export const managedConversations: Writable<ConversationMetadata[]> = writable(loadConversationsFromStorage());

// Subscribe to changes in the store and save them back to localStorage
managedConversations.subscribe(value => {
    // Avoid saving the initial empty array if loaded state is empty
    // This prevents overwriting potentially valid stored data on initial load if parsing failed
    // A more robust approach might involve checking if the load was successful
    if (value.length > 0 || localStorage.getItem(LOCAL_STORAGE_KEY)) {
	    saveConversationsToStorage(value);
    }
});


// --- Management Functions ---

/** Creates a new conversation entry and adds it to the store */
export function createNewConversation(name: string = "New Chat"): ConversationMetadata {
	const newConversation: ConversationMetadata = {
		id: uuidv4(),
		name: name,
		thread_id: null, // Will be set after first backend interaction
		created_at: new Date().toISOString(),
		last_updated_at: new Date().toISOString(),
		last_used_constitution_ids: [], // Initially empty
        preview: ""
	};

	managedConversations.update(list => [newConversation, ...list]); // Add to the beginning
	return newConversation;
}

/** Updates specific fields of an existing conversation */
export function updateConversation(id: string, updates: Partial<Omit<ConversationMetadata, 'id' | 'created_at'>>) {
    managedConversations.update(list =>
        list.map(conv => {
            if (conv.id === id) {
                // Ensure last_updated_at is always set on update
                return { ...conv, ...updates, last_updated_at: new Date().toISOString() };
            }
            return conv;
        }).sort((a, b) => new Date(b.last_updated_at).getTime() - new Date(a.last_updated_at).getTime()) // Re-sort after update
    );
}


/** Deletes a conversation by its client-side ID */
export function deleteConversation(id: string) {
	managedConversations.update(list => list.filter(conv => conv.id !== id));
}

/** Finds a conversation by its client-side ID */
export function findConversationById(id: string): ConversationMetadata | undefined {
    let found: ConversationMetadata | undefined;
    managedConversations.subscribe(list => { // Use subscribe to get current value
        found = list.find(conv => conv.id === id);
    })(); // Immediately invoke to unsubscribe after getting value
    return found;
}

/** Finds a conversation by its backend thread_id */
export function findConversationByThreadId(thread_id: string): ConversationMetadata | undefined {
     let found: ConversationMetadata | undefined;
    managedConversations.subscribe(list => {
        found = list.find(conv => conv.thread_id === thread_id);
    })();
    return found;
}

/**
 * Gets or creates conversation metadata for a given backend thread_id.
 * Useful when loading a thread directly (e.g., from a URL or initial load).
 */
export function getOrCreateConversationForThread(thread_id: string, initialName: string = "Loaded Chat"): ConversationMetadata {
    let conversation = findConversationByThreadId(thread_id);
    if (!conversation) {
        console.warn(`No local metadata found for thread_id ${thread_id}. Creating new entry.`);
        conversation = createNewConversation(initialName);
        // Immediately update the thread_id for the newly created entry
        updateConversation(conversation.id, { thread_id: thread_id });
        // Need to get the updated object reference
        conversation = findConversationById(conversation.id)!;
    }
    return conversation;
}

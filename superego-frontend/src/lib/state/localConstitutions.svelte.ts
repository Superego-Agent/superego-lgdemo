import { nanoid } from 'nanoid';
import { persistedLocalState, PersistedLocalState } from '$lib/utils/persistedLocalState.svelte'; // Import type

// --- Constants for LocalStorage Keys ---
const LOCAL_CONSTITUTIONS_KEY = 'superego_local_constitutions';

export class LocalConstitutionsStateStore {
    // --- Helper to define persisted properties ---
    #definePersisted<T>(propName: keyof this, storageKey: string, defaultValue: T): PersistedLocalState<T> {
        const persisted = persistedLocalState<T>(storageKey, defaultValue);
        Object.defineProperty(this, propName, {
            get: () => persisted.state,
            set: (value: T) => { persisted.state = value; },
            enumerable: true,
            configurable: true
        });
        return persisted;
    }

    // --- Public Property Declarations (Types) ---
    localConstitutions!: LocalConstitution[];

    constructor() {
        this.#definePersisted('localConstitutions', LOCAL_CONSTITUTIONS_KEY, []);
    }

    // --- Methods for State Mutation ---

    /** Adds a new local constitution to the store. */
    addLocalConstitution(title: string, text: string): LocalConstitution {
        const newConstitution: LocalConstitution = {
            id: nanoid(), // Generate unique local ID
            title: title.trim(),
            text: text, // Keep original text formatting
            createdAt: new Date().toISOString(),
        };
        this.localConstitutions.push(newConstitution); // Use direct access (setter triggers mutation)
        console.log(`[OK] Added local constitution: ${newConstitution.id} (${newConstitution.title})`);
        return newConstitution;
    }

    /** Updates an existing local constitution by its ID. */
    updateLocalConstitution(id: string, title: string, text: string): boolean {
        // Use direct access (getter)
        const index = this.localConstitutions.findIndex(c => c.id === id);
        if (index !== -1) {
            const updatedConstitution = {
                ...this.localConstitutions[index], // Use this.localConstitutions
                title: title.trim(),
                text: text,
            };
            // Create new array for update as direct mutation of item in array might not trigger setter
            const newList = [...this.localConstitutions];
            newList[index] = updatedConstitution;
            this.localConstitutions = newList; // Trigger setter
            console.log(`[OK] Updated local constitution: ${id}`);
            return true;
        }
        console.warn(`Attempted update on non-existent local constitution: ${id}`);
        return false;
    }

    /** Deletes a local constitution by its ID. */
    deleteLocalConstitution(id: string): boolean {
        // Use direct access (getter) and filter for immutable update
        const initialLength = this.localConstitutions.length;
        const filtered = this.localConstitutions.filter(c => c.id !== id);
        if (filtered.length < initialLength) {
            this.localConstitutions = filtered; // Trigger setter
            console.log(`[OK] Deleted local constitution: ${id}`);
            return true;
        }
        console.warn(`Attempted delete on non-existent local constitution: ${id}`);
        return false;
    }
}

// --- Export Singleton Instance ---
export const localConstitutionsStore = new LocalConstitutionsStateStore();
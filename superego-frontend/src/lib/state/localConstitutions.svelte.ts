import { nanoid } from 'nanoid';
import { persistedLocalState } from '$lib/utils/persistedLocalState.svelte';

// --- Constants for LocalStorage Keys ---
const LOCAL_CONSTITUTIONS_KEY = 'superego_local_constitutions';

export class LocalConstitutionsStateStore {
    /** User-defined local constitutions. Persisted. */
    localConstitutions = persistedLocalState<LocalConstitution[]>(LOCAL_CONSTITUTIONS_KEY, []);

    constructor() {} // No constructor logic needed due to persistedLocalState

    // --- Methods for State Mutation ---

    /** Adds a new local constitution to the store. */
    addLocalConstitution(title: string, text: string): LocalConstitution {
        const newConstitution: LocalConstitution = {
            id: nanoid(), // Generate unique local ID
            title: title.trim(),
            text: text, // Keep original text formatting
            createdAt: new Date().toISOString(),
        };
        this.localConstitutions.state.push(newConstitution);
        console.log(`[OK] Added local constitution: ${newConstitution.id} (${newConstitution.title})`);
        return newConstitution;
    }

    /** Updates an existing local constitution by its ID. */
    updateLocalConstitution(id: string, title: string, text: string): boolean {
        const currentConstitutions = this.localConstitutions.state;
        const index = currentConstitutions.findIndex(c => c.id === id);
        if (index !== -1) {
            const updatedConstitution = {
                ...currentConstitutions[index],
                title: title.trim(),
                text: text,
            };
            this.localConstitutions.state[index] = updatedConstitution;
            console.log(`[OK] Updated local constitution: ${id}`);
            return true;
        }
        console.warn(`Attempted update on non-existent local constitution: ${id}`);
        return false;
    }

    /** Deletes a local constitution by its ID. */
    deleteLocalConstitution(id: string): boolean {
        const currentConstitutions = this.localConstitutions.state;
        const initialLength = currentConstitutions.length;
        // Find index and use splice for direct mutation
        const indexToDelete = currentConstitutions.findIndex(c => c.id === id);
        if (indexToDelete !== -1) {
            this.localConstitutions.state.splice(indexToDelete, 1);
            console.log(`[OK] Deleted local constitution: ${id}`);
            return true;
        }
        console.warn(`Attempted delete on non-existent local constitution: ${id}`);
        return false;
    }
}

// --- Export Singleton Instance ---
export const localConstitutionsStore = new LocalConstitutionsStateStore();
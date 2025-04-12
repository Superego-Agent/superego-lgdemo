import { nanoid } from 'nanoid';
import { persistedLocalState, PersistedLocalState } from '$lib/utils/persistedLocalState.svelte'; // Import type
import { fetchAvailableConstitutions } from '$lib/api/rest.svelte';

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
    addItem(title: string, text: string): LocalConstitution {
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
    updateItem(id: string, title: string, text: string): boolean {
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
    deleteItem(id: string): boolean {
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

export class GlobalConstitutionsStore {
    // --- State Properties ---
    constitutions = $state<ConstitutionItem[]>([]);
    isLoading = $state<boolean>(false);
    error = $state<string | null>(null);
    #hasLoaded = $state<boolean>(false); // Private state to prevent multiple fetches

    // --- Methods ---

    /**
     * Fetches the global constitutions from the API and updates the store state.
     * Should typically be called once, e.g., on application load.
     */
    async load(): Promise<void> {
        if (this.#hasLoaded || this.isLoading) {
            // Already loaded or currently loading, do nothing
            return;
        }

        this.isLoading = true;
        this.error = null;
        this.#hasLoaded = true; // Set flag immediately

        try {
            const fetchedConstitutions = await fetchAvailableConstitutions();
            // Filter out 'none' if present in the fetched data
            this.constitutions = fetchedConstitutions.filter((c: ConstitutionItem) => c.id !== 'none');
        } catch (err: any) {
            console.error("Failed to load global constitutions:", err);
            this.error = err.message || "Unknown error fetching global constitutions.";
            this.#hasLoaded = false; // Reset flag on error to allow retry
        } finally {
            this.isLoading = false;
        }
    }

    // --- Derived State (Example, if needed) ---
    // get constitutionNames(): string[] {
    //     return this.constitutions.map(c => c.name);
    // }
}

// --- Export Singleton Instances ---
export const localConstitutionsStore = new LocalConstitutionsStateStore();
export const globalConstitutionsStore = new GlobalConstitutionsStore();
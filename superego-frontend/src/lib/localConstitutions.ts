import { writable, get } from 'svelte/store';
import { nanoid } from 'nanoid';

// Use a specific key for local storage
const LOCAL_STORAGE_KEY = 'superego_local_constitutions';

// --- Store ---
// Initialize with an empty array, load attempts to fill it
export const localConstitutionsStore = writable<LocalConstitution[]>([]);

// --- Helper Functions ---

/** Saves the current state of the local constitutions store to localStorage. */
function saveLocalConstitutions(): void {
    try {
        const constitutions = get(localConstitutionsStore);
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(constitutions));
    } catch (error) {
        console.error("Failed to save local constitutions to localStorage:", error);
        // Optionally, notify the user via a global error store or other mechanism
    }
}

// --- Public API ---

/** Loads constitutions from localStorage into the store. Should be called on app startup. Returns a promise to indicate completion/error. */
export async function loadLocalConstitutions(): Promise<void> {
    try {
        // No need to await localStorage.getItem as it's synchronous
        const storedData = localStorage.getItem(LOCAL_STORAGE_KEY);
        if (storedData) {
            const parsedData: LocalConstitution[] = JSON.parse(storedData);
            // Basic validation could be added here (e.g., check if it's an array)
            if (Array.isArray(parsedData)) {
                localConstitutionsStore.set(parsedData);
            } else {
                console.warn("Invalid data found in localStorage for local constitutions. Resetting.");
                localStorage.removeItem(LOCAL_STORAGE_KEY); // Clear invalid data
                localConstitutionsStore.set([]);
            }
        } else {
            localConstitutionsStore.set([]); // Ensure store is empty if nothing is in storage
        }
    } catch (error) {
        console.error("Failed to load local constitutions from localStorage:", error);
        localConstitutionsStore.set([]); // Reset store on error
        // Optionally, clear potentially corrupted storage item
        // localStorage.removeItem(LOCAL_STORAGE_KEY);
    }
}

/** Adds a new local constitution to the store and saves to localStorage. */
export function addLocalConstitution(title: string, text: string): LocalConstitution {
    const newConstitution: LocalConstitution = {
        id: nanoid(), // Generate unique local ID
        title: title.trim(),
        text: text, // Keep original text formatting
        createdAt: new Date().toISOString(),
    };

    localConstitutionsStore.update(constitutions => {
        // Add to the beginning or end based on preference (e.g., end)
        return [...constitutions, newConstitution];
    });

    saveLocalConstitutions(); // Persist changes
    return newConstitution;
}

/** Updates an existing local constitution by its ID. */
export function updateLocalConstitution(id: string, title: string, text: string): boolean {
    let updated = false;
    localConstitutionsStore.update(constitutions => {
        const index = constitutions.findIndex(c => c.id === id);
        if (index !== -1) {
            constitutions[index] = {
                ...constitutions[index],
                title: title.trim(),
                text: text,
                // Optionally update a 'lastUpdatedAt' field here if added to the interface
            };
            updated = true;
            return [...constitutions]; // Return new array for reactivity
        }
        return constitutions; // Return original array if not found
    });

    if (updated) {
        saveLocalConstitutions(); // Persist changes if update occurred
    }
    return updated;
}

/** Deletes a local constitution by its ID. */
export function deleteLocalConstitution(id: string): boolean {
    let deleted = false; // Declare deleted variable outside the update scope
    localConstitutionsStore.update(constitutions => {
        const initialLength = constitutions.length;
        const filtered = constitutions.filter(c => c.id !== id);
        deleted = filtered.length < initialLength; // Assign to the outer variable
        return filtered; // Return the filtered array
    });

    if (deleted) {
        saveLocalConstitutions(); // Persist changes if deletion occurred
    }
    return deleted;
}

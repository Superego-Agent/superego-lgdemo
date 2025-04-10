import { writable, get } from 'svelte/store'; // Added get
import type { Writable } from 'svelte/store';
import { fetchAvailableConstitutions } from '../api'; // Assuming api.ts is one level up

// Store for the list of global constitutions
export const globalConstitutions: Writable<ConstitutionItem[]> = writable([]);

// Store for loading state
export const isLoadingGlobalConstitutions: Writable<boolean> = writable(false);

// Store for error state
export const globalConstitutionsError: Writable<string | null> = writable(null);

let hasLoaded = false; // Prevent multiple fetches

/**
 * Fetches the global constitutions from the API and updates the stores.
 * Should typically be called once, e.g., on application load.
 */
export async function loadGlobalConstitutions(): Promise<void> {
    if (hasLoaded || get(isLoadingGlobalConstitutions)) {
        // Already loaded or currently loading, do nothing
        return;
    }

    isLoadingGlobalConstitutions.set(true);
    globalConstitutionsError.set(null);
    hasLoaded = true; // Set flag immediately to prevent race conditions

    try {
        const constitutions = await fetchAvailableConstitutions();
        // Filter out 'none' if present in the fetched data
        const filteredConstitutions = constitutions.filter((c: ConstitutionItem) => c.id !== 'none');
        globalConstitutions.set(filteredConstitutions);
    } catch (err: any) {
        console.error("Failed to load global constitutions:", err);
        globalConstitutionsError.set(err.message || "Unknown error fetching global constitutions.");
        hasLoaded = false; // Reset flag on error to allow retry? Or handle retry differently? For now, reset.
    } finally {
        isLoadingGlobalConstitutions.set(false);
    }
}

// Helper function to get a constitution title by ID from either global or local store
// Note: This might be better placed elsewhere or handled differently depending on usage.
// import { get } from 'svelte/store'; // Add if using get outside component
// import { localConstitutionsStore } from '../localConstitutions';
// export function getConstitutionTitleById(id: string): string | undefined {
//     const globalList = get(globalConstitutions);
//     const localList = get(localConstitutionsStore);
//     const foundGlobal = globalList.find(c => c.id === id);
//     if (foundGlobal) return foundGlobal.title;
//     const foundLocal = localList.find(c => c.id === id);
//     return foundLocal?.title;
// }
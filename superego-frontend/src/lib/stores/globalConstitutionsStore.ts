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

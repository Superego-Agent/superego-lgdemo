import { writable, get } from 'svelte/store';
import type { Writable } from 'svelte/store';
import { streamRun } from '../api';
import { globalError } from '../stores';
// Types from global.d.ts are globally available

/**
 * Store to hold the currently selected constitution modules.
 */
const currentRunConfigModules: Writable<ConfiguredConstitutionModule[]> = writable([]);

/**
 * Updates the stored configuration modules.
 * Typically called when the ConstitutionSelector dispatches a change.
 * @param config - The array of configured constitution modules.
 */
export function updateChatConfig(config: ConfiguredConstitutionModule[]): void {
    currentRunConfigModules.set(config);
}

/**
 * Sends the user's input to the backend via the streamRun API.
 * Uses the currently stored configuration modules to build the RunConfig.
 * @param userInput - The text entered by the user.
 */
export async function sendUserMessage(userInput: string): Promise<void> {
    const modules = get(currentRunConfigModules);
    const runConfig: RunConfig = {
        configuredModules: modules
    };

    console.log(`[chatService] Triggering streamRun with config:`, runConfig);
    globalError.set(null); // Clear global error before sending

    try {
        await streamRun(userInput, runConfig);
    } catch (error: unknown) {
        console.error("[chatService] Error occurred during streamRun call:", error);
        // The error should ideally be handled within streamRun/api.ts and reflected
        // in the threadCacheStore or globalError store appropriately.
        // We might set globalError here as a fallback if api.ts doesn't catch it.
        if (error instanceof Error) {
             globalError.set(`Failed to send message: ${error.message}`);
        } else {
             globalError.set("Failed to send message due to an unknown error.");
        }
    }
}
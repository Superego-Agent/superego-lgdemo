import { streamRun } from '$lib/api/sse.svelte';
import { activeStore } from '$lib/state/active.svelte';
import { sessionStore } from '$lib/state/session.svelte';
import { constitutionStore } from '$lib/state/constitutions.svelte'; // <-- Import constitutionStore

// Helper function (similar to RunConfigurationPanel) - needs to be defined or imported
function findMetadataById(id: string): LocalConstitutionMetadata | RemoteConstitutionMetadata | null {
    // This is a placeholder implementation. Ideally, use a more efficient lookup
    // if constitutionStore provides one (e.g., a map or flat list).
    function searchTree(nodes: UINode[]): LocalConstitutionMetadata | RemoteConstitutionMetadata | null {
        for (const node of nodes) {
            if (node.type === 'file') {
                const meta = node.metadata;
                const backendId = meta.source === 'remote' ? meta.relativePath : meta.localStorageKey;
                if (backendId === id) {
                    return meta;
                }
            } else if (node.type === 'folder') {
                const found = searchTree(node.children);
                if (found) return found;
            }
        }
        return null;
    }
    // Ensure constitutionStore.displayTree is accessed correctly if it's reactive
    // If constitutionStore is a Svelte 5 runes-based store, direct access might be fine.
    // If it's a legacy store, you might need get(constitutionStore).displayTree
    return searchTree(constitutionStore.displayTree);
}


/**
 * Sends the user's input to the backend via the streamRun API.
 * @param userInput - The text entered by the user.
 */
export async function sendUserMessage(userInput: string): Promise<void> {
    activeStore.clearGlobalError(); 

    const currentSessionId = sessionStore.activeSessionId; 
    if (!currentSessionId) {
        console.error("[chatService] Cannot send message: No active session ID.");
        activeStore.setGlobalError("No active session selected."); // Use method to set error
        return;
    }

    const currentSessionData = currentSessionId ? sessionStore.uiSessions[currentSessionId] : null; 
    if (!currentSessionData || !currentSessionData.threads) {
        console.error(`[chatService] Cannot send message: Session state or threads not found for ID ${currentSessionId}.`);
        activeStore.setGlobalError("Session data not found."); // Use method to set error
        return;
    }

    const enabledConfigs = Object.entries(currentSessionData.threads)
        .filter(([_, config]) => (config as ThreadConfigState).isEnabled) as [string, ThreadConfigState][];

    if (enabledConfigs.length === 0) {
        console.warn("[chatService] No enabled configurations to run.");
        activeStore.setGlobalError("No configurations enabled to run."); // Use method to set error
        return;
    }

    console.log(`[chatService] Sending message to ${enabledConfigs.length} enabled configurations for session ${currentSessionId}.`);

    // Sequentially initiate runs for each enabled config
    // Backend handles concurrency
    for (const [threadId, config] of enabledConfigs) {
        console.log(`[chatService] Initiating run for thread ${threadId} with original config:`, config.runConfig); // Keep original log

        const apiRunConfigPayload: RunConfig = {
            configuredModules: config.runConfig?.configuredModules?.map(module => {
                if (module.text !== undefined) {
                    // Local: Return object with text
                    return {
                        title: module.title,
                        adherence_level: module.adherence_level,
                        text: module.text
                    };
                } else if (module.relativePath !== undefined) {
                    // Remote: Return object with relativePath
                    return {
                        title: module.title,
                        adherence_level: module.adherence_level,
                        relativePath: module.relativePath 
                    };
                } else {
                    console.warn("[chatService] Skipping constitution module with invalid structure:", module);
                    return null;
                }
            }).filter((module): module is ConfiguredConstitutionModule => module !== null) ?? []
        };


        try {
            // Call streamRun with the correctly typed payload
            await streamRun(userInput, apiRunConfigPayload, threadId);
        } catch (error: unknown) {
            // Log error for this specific run but continue trying others
            console.error(`[chatService] Error initiating run for thread ${threadId}:`, error);
            // Optionally set a specific error state for this thread in threadCacheStore later
        }
    }
}

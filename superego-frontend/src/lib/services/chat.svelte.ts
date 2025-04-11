import { streamRun } from '../api/sse.svelte';
import { appState } from '../state/app.svelte';
import { sessionState } from '../state/session.svelte';

/**
 * Sends the user's input to the backend via the streamRun API.
 * Uses the currently stored configuration modules to build the RunConfig.
 * @param userInput - The text entered by the user.
 */
export async function sendUserMessage(userInput: string): Promise<void> {
    appState.globalError = null;

    const currentSessionId = sessionState.activeSessionId;
    if (!currentSessionId) {
        console.error("[chatService] Cannot send message: No active session ID.");
        appState.globalError = "No active session selected.";
        return;
    }

    const currentSessionData = sessionState.uiSessions[currentSessionId]; // Renamed variable
    if (!currentSessionData || !currentSessionData.threads) {
        console.error(`[chatService] Cannot send message: Session state or threads not found for ID ${currentSessionId}.`);
        appState.globalError = "Session data not found.";
        return;
    }

    const enabledConfigs = Object.entries(currentSessionData.threads)
        .filter(([_, config]) => (config as ThreadConfigState).isEnabled);

    if (enabledConfigs.length === 0) {
        console.warn("[chatService] No enabled configurations to run.");
        appState.globalError = "No configurations enabled to run.";
        return;
    }

    console.log(`[chatService] Sending message to ${enabledConfigs.length} enabled configurations for session ${currentSessionId}.`);

    // Sequentially initiate runs for each enabled config
    // Backend handles concurrency
    for (const [threadId, config] of enabledConfigs) {
        console.log(`[chatService] Initiating run for thread ${threadId} with config:`, (config as ThreadConfigState).runConfig);
        try {
            // Call the updated streamRun, passing the specific threadId and runConfig
            await streamRun(userInput, (config as ThreadConfigState).runConfig, threadId);
        } catch (error: unknown) {
            // Log error for this specific run but continue trying others
            console.error(`[chatService] Error initiating run for thread ${threadId}:`, error);
            // Optionally set a specific error state for this thread in threadCacheStore later
            // For now, just log it. Global error might be set by api.ts if it's a setup issue.
        }
    }
}
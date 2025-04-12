<script lang="ts">
    // Component to display and manage multiple Run Configuration cards (e.g., Superego A, B)
    import { sessionStore } from '../state/session.svelte'; // Import new session state
    import { activeStore } from "$lib/state/active.svelte"; // Import new active store
    import ConfigCard from './ConfigCard.svelte';
    import { v4 as uuidv4 } from 'uuid'; // For generating new config IDs

    // Reactive access to the current session's configurations
    // Access .state for persisted stores in derived
    let currentSessionId = $derived(sessionStore.activeSessionId); // Access directly
    let currentSession = $derived(currentSessionId ? sessionStore.uiSessions[currentSessionId] : null); // Access directly
    let threadConfigs = $derived(currentSession?.threads ?? {});
    let configEntries = $derived(Object.entries(threadConfigs));

    function handleCardSelect(event: CustomEvent<{ threadId: string }>) {
        const selectedThreadId = event.detail.threadId;
        if (currentSessionId) {
            activeStore.setActiveConfigEditor(selectedThreadId); // Use method on activeStore
        }
    }

    function addConfiguration() {
        if (!currentSessionId) return;

        const newThreadId = uuidv4();
        const newConfig: ThreadConfigState = {
            name: `Config ${Object.keys(threadConfigs).length + 1}`, // Simple default name
            runConfig: { // Default empty runConfig - might need refinement
                configuredModules: []
            },
            isEnabled: true // Default to enabled
        };

        // Use .state for persisted store and direct mutation
        // Use .state and immutable update pattern
        if (currentSessionId && sessionStore.uiSessions[currentSessionId]) { // Access directly
            const sessionToUpdate = sessionStore.uiSessions[currentSessionId]; // Access directly
            const updatedThreads = { ...sessionToUpdate.threads, [newThreadId]: newConfig };
            const updatedSession = { ...sessionToUpdate, threads: updatedThreads, lastUpdatedAt: new Date().toISOString() };
            sessionStore.uiSessions = { ...sessionStore.uiSessions, [currentSessionId]: updatedSession }; // Access directly (setter)
            activeStore.setActiveConfigEditor(newThreadId); // Use method on activeStore
        } else {
            console.warn("RunConfigManager: Cannot add configuration, no active session found in store.");
        }
    }

    // --- Functions for managing configurations ---
    function deleteConfiguration(threadId: string) {
        // Use the derived currentSessionId from the top scope
        if (currentSessionId && sessionStore.uiSessions[currentSessionId]?.threads?.[threadId]) {
            const sessionToUpdate = sessionStore.uiSessions[currentSessionId];
            const updatedThreads = { ...sessionToUpdate.threads };
            delete updatedThreads[threadId];
            const updatedSession = { ...sessionToUpdate, threads: updatedThreads, lastUpdatedAt: new Date().toISOString() };
            sessionStore.uiSessions = { ...sessionStore.uiSessions, [currentSessionId]: updatedSession };

            // If the deleted config was active, select another one if possible
            if (activeStore.activeConfigEditorId === threadId) { // Use activeStore
                const remainingIds = Object.keys(updatedThreads);
                activeStore.setActiveConfigEditor(remainingIds.length > 0 ? remainingIds[0] : null); // Use method on activeStore
            }
        } else {
            console.warn(`RunConfigManager: Cannot delete configuration ${threadId}, session or thread not found.`);
        }
    }

    function renameConfiguration(threadId: string, newName: string) {
        // Use the derived currentSessionId from the top scope
        if (currentSessionId && sessionStore.uiSessions[currentSessionId]?.threads?.[threadId]) {
            const sessionToUpdate = sessionStore.uiSessions[currentSessionId];
            const threadToUpdate = sessionToUpdate.threads[threadId];
            if (threadToUpdate.name !== newName) {
                const updatedThread = { ...threadToUpdate, name: newName };
                const updatedSession = { ...sessionToUpdate, threads: { ...sessionToUpdate.threads, [threadId]: updatedThread }, lastUpdatedAt: new Date().toISOString() };
                sessionStore.uiSessions = { ...sessionStore.uiSessions, [currentSessionId]: updatedSession };
            }
        } else {
             console.warn(`RunConfigManager: Cannot rename configuration ${threadId}, session or thread not found.`);
        }
    }

     function toggleConfiguration(threadId: string, isEnabled: boolean) {
        // Use the derived currentSessionId from the top scope
        if (currentSessionId && sessionStore.uiSessions[currentSessionId]?.threads?.[threadId]) {
             const sessionToUpdate = sessionStore.uiSessions[currentSessionId];
            const threadToUpdate = sessionToUpdate.threads[threadId];
            if (threadToUpdate.isEnabled !== isEnabled) {
                const updatedThread = { ...threadToUpdate, isEnabled: isEnabled };
                const updatedSession = { ...sessionToUpdate, threads: { ...sessionToUpdate.threads, [threadId]: updatedThread }, lastUpdatedAt: new Date().toISOString() };
                sessionStore.uiSessions = { ...sessionStore.uiSessions, [currentSessionId]: updatedSession };
            }
        } else {
             console.warn(`RunConfigManager: Cannot toggle configuration ${threadId}, session or thread not found.`);
        }
    }
</script>

<div class="run-config-manager">
    <div class="cards-container">
        {#each configEntries as [threadId, config] (threadId)}
            <ConfigCard
                {threadId}
                config={config as ThreadConfigState}
                isActive={activeStore.activeConfigEditorId === threadId}
                on:select={handleCardSelect}
                on:delete={() => deleteConfiguration(threadId)}
                on:rename={(e) => renameConfiguration(threadId, e.detail.newName)}
                on:toggle={(e) => toggleConfiguration(threadId, e.detail.isEnabled)}
            />
        {/each}
        
        <button class="add-button" onclick={addConfiguration} title="Add new configuration">
            + Add
        </button>
    </div>
</div>

<!-- Removed duplicated functions -->

<style lang="scss">
    .run-config-manager {
        display: flex;
        flex-direction: column;
        gap: var(--space-sm);
        padding: var(--space-sm) 0; // Add some padding
        border-bottom: 1px solid var(--border-color-light); // Separator
        margin-bottom: var(--space-sm); // Space below
    }

    .cards-container {
        display: flex;
        flex-wrap: wrap; // Allow cards to wrap
        gap: var(--space-sm);
        align-items: stretch;
    }

    .add-button {
        margin: 0px;
        height: 100%;
        padding: var(--space-xs) var(--space-sm);
        background-color: var(--bg-secondary);
        border: 2px dashed var(--secondary);
        border-radius: var(--radius-sm);
        cursor: pointer;
        color: var(--text-secondary);

        &:hover {
            background-color: var(--bg-hover);
            color: var(--text-primary);
        }
    }
</style>
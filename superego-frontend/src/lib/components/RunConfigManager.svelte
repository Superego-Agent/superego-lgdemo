<!-- Component to display and manage multiple Run Configuration cards (Config 1, Config 2) -->

<script lang="ts">
    import { sessionStore } from '../state/session.svelte'; 
    import { activeStore } from "$lib/state/active.svelte"; 
    import ConfigCard from './ConfigCard.svelte';
    import IconAdd from '~icons/fluent/add-24-regular'; 
    import { v4 as uuidv4 } from 'uuid'; 

    let currentSessionId = $derived(sessionStore.activeSessionId);
    let currentSession = $derived(currentSessionId ? sessionStore.uiSessions[currentSessionId] : null);
    let threadConfigs = $derived(currentSession?.threads ?? {});
    let configEntries = $derived(Object.entries(threadConfigs));

    function handleCardSelect(detail: { threadId: string }) {
        const selectedThreadId = detail.threadId;
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

        if (currentSessionId && sessionStore.uiSessions[currentSessionId]) { 
            const sessionToUpdate = sessionStore.uiSessions[currentSessionId]; 
            const updatedThreads = { ...sessionToUpdate.threads, [newThreadId]: newConfig };
            const updatedSession = { ...sessionToUpdate, threads: updatedThreads, lastUpdatedAt: new Date().toISOString() };
            sessionStore.uiSessions = { ...sessionStore.uiSessions, [currentSessionId]: updatedSession }; 
            activeStore.setActiveConfigEditor(newThreadId);
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
            if (activeStore.activeConfigEditorId === threadId) { 
                const remainingIds = Object.keys(updatedThreads);
                activeStore.setActiveConfigEditor(remainingIds.length > 0 ? remainingIds[0] : null); 
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
                onSelect={handleCardSelect}
                onToggle={(e) => toggleConfiguration(threadId, e.isEnabled)}
            />
        {/each}
        
        <button class="add-button" onclick={addConfiguration} title="Add new configuration">
            <IconAdd /> Add
        </button>
    </div>
</div>

<style lang="scss">
    .run-config-manager {
        display: flex;
        flex-direction: column;
        gap: var(--space-sm);
        padding: var(--space-sm); // Add horizontal padding
        border-bottom: 1px solid var(--border-color-light); // Separator
        margin-bottom: var(--space-sm); // Space below
    }

    .cards-container {
        display: grid;
        // grid-template-columns: repeat(4, minmax(100px, 1fr)); // Old fixed column layout
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); // Responsive grid, min 200px, max flexible
        gap: var(--space-sm);
        align-items: stretch; // Ensure cards stretch vertically to fill row height
    }

    .add-button {
        margin: 0px;
        // height: 100%; // Let min-height handle vertical size
        min-height: 100px; // Ensure minimum height
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

    .add-button {
        display: inline-flex;
        align-items: center;
        justify-content: center; // Center icon and text horizontally
        gap: var(--space-xxs);

    }
</style>
<script lang="ts">
    // Component to display and manage multiple Run Configuration cards (e.g., Superego A, B)
    import { persistedActiveSessionId, persistedUiSessions } from '../stores.svelte'; 
    import { uiState } from "$lib/stores/uiState.svelte";
    import ConfigCard from './ConfigCard.svelte';
    import { v4 as uuidv4 } from 'uuid'; // For generating new config IDs

    // Reactive access to the current session's configurations
    // Access .state for persisted stores in derived
    let currentSessionId = $derived(persistedActiveSessionId.state);
    let currentSession = $derived(currentSessionId ? persistedUiSessions.state[currentSessionId] : null);
    let threadConfigs = $derived(currentSession?.threads ?? {});
    let configEntries = $derived(Object.entries(threadConfigs));

    function handleCardSelect(event: CustomEvent<{ threadId: string }>) {
        const selectedThreadId = event.detail.threadId;
        if (currentSessionId) {
            uiState.activeConfigEditorId = selectedThreadId;
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
        if (currentSessionId && persistedUiSessions.state[currentSessionId]) {
            persistedUiSessions.state[currentSessionId].threads[newThreadId] = newConfig;
            uiState.activeConfigEditorId = newThreadId;
        } else {
            console.warn("RunConfigManager: Cannot add configuration, no active session found in store.");
        }
    }

</script>

<div class="run-config-manager">
    <div class="cards-container">
        
        {#each configEntries as [threadId, config] (threadId)}
            <ConfigCard
                {threadId}
                config={config as ThreadConfigState}
                isActive={uiState.activeConfigEditorId === threadId}
                on:select={handleCardSelect}
            />
        {/each}
        <button class="add-button" onclick={addConfiguration} title="Add new configuration">
            + Add 
        </button>
    </div>

</div>

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
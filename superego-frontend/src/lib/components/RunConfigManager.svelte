<script lang="ts">
    // Component to display and manage multiple Run Configuration cards (e.g., Superego A, B)
    import { activeSessionId, uiSessions } from '../stores'; 
    import { activeConfigEditorId } from "$lib/stores/uiState";
    import ConfigCard from './ConfigCard.svelte';
    import { createEventDispatcher } from 'svelte';
    import { v4 as uuidv4 } from 'uuid'; // For generating new config IDs

    const dispatch = createEventDispatcher();

    // Reactive access to the current session's configurations
    $: currentSessionId = $activeSessionId;
    $: currentSession = currentSessionId ? $uiSessions[currentSessionId] : null;
    $: threadConfigs = currentSession?.threads ?? {};
    $: configEntries = Object.entries(threadConfigs); // [threadId, ThreadConfigState][]

    function handleCardSelect(event: CustomEvent<{ threadId: string }>) {
        const selectedThreadId = event.detail.threadId;
        if (currentSessionId) {
            activeConfigEditorId.set(selectedThreadId);
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

        uiSessions.update(sessions => {
            if (sessions[currentSessionId]) {
                // Add the new configuration
                sessions[currentSessionId].threads = {
                    ...sessions[currentSessionId].threads,
                    [newThreadId]: newConfig
                };
            }
            activeConfigEditorId.set(newThreadId);
            return sessions;
        });
    }

</script>

<div class="run-config-manager">
    <div class="cards-container">
        
        {#each configEntries as [threadId, config] (threadId)}
            <ConfigCard
                {threadId}
                {config}
                isActive={$activeConfigEditorId === threadId}
                on:select={handleCardSelect}
            />
        {/each}
        <button class="add-button" on:click={addConfiguration} title="Add new configuration">
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
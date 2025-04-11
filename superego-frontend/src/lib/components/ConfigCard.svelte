<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    // Types from global.d.ts are globally available

    export let threadId: string;
    export let config: ThreadConfigState;
    export let isActive: boolean = false;

    const dispatch = createEventDispatcher();

    function handleClick() {
        dispatch('select', { threadId });
    }

</script>

<button
    class="config-card"
    class:active={isActive}
    on:click={handleClick}
    title={`Select configuration: ${config.name}`}
>
    <span class="config-name">{config.name}</span>
    {#if !config.isEnabled}
        <span class="disabled-indicator" title="This configuration is disabled and won't run">(Disabled)</span>
    {/if}
</button>

<style lang="scss">
    .config-card {
        padding: var(--space-sm) var(--space-md);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        background-color: var(--bg-secondary);
        cursor: pointer;
        transition: all 0.2s ease-in-out;
        display: flex;
        align-items: center;
        gap: var(--space-xs);
        min-width: 100px; 

        &:hover {
            border-color: var(--primary-light);
            background-color: var(--bg-hover);
        }

        &.active {
            border-color: var(--primary);
            background-color: var(--primary-bg-subtle); // A subtle background for active
            box-shadow: 0 0 0 2px var(--primary-light);
            color: var(--primary);
        }
    }

    .config-name {
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex-grow: 1; // Allow name to take space
    }
    .disabled-indicator {
        font-size: 0.8em;
        color: var(--text-disabled);
        font-style: italic;
        white-space: nowrap;
    }

</style>
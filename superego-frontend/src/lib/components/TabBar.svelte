<script lang="ts">
    export let activeTab: string;
    const tabs = [
        { id: 'home', label: 'Home' },
        { id: 'add-constitution', label: 'Add Constitution' }
    ];
</script>

<div class="tab-bar">
    {#each tabs as tab}
        <button 
            class="tab-button {activeTab === tab.id ? 'active' : ''}"
            on:click={() => activeTab = tab.id}
        >
            {tab.label}
        </button>
    {/each}
</div>

<style>
    .tab-bar {
        display: flex;
        gap: 1px;
        background-color: var(--bg-elevated);
        padding: 0 16px;
        border-bottom: 1px solid var(--input-border);
    }

    .tab-button {
        padding: 12px 24px;
        border: none;
        background: none;
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 14px;
        position: relative;
        transition: color 0.2s;
    }

    .tab-button:hover {
        color: var(--text-primary);
    }

    .tab-button.active {
        color: var(--primary);
    }

    .tab-button.active::after {
        content: '';
        position: absolute;
        bottom: -1px;
        left: 0;
        right: 0;
        height: 2px;
        background-color: var(--primary);
    }
</style> 
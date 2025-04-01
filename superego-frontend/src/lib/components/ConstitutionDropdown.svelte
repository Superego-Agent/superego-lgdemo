<script lang="ts">
    import { availableConstitutions, activeConstitutionIds } from '../stores';
    import { slide, scale, fade } from 'svelte/transition';
</script>

<div class="constitution-selector use-mode">
    <p class="select-prompt">Select constitutions to apply:</p>

    <div class="select-container">
        <select 
            multiple 
            bind:value={$activeConstitutionIds} 
            class="constitution-select"
        >
            {#each $availableConstitutions as constitution (constitution.id)}
                <option value={constitution.id} title={constitution.description}>
                    {constitution.name} ({constitution.id})
                </option>
            {/each}
        </select>
    </div>

    <div class="selected-chips">
        <div class="chips-header">
            <span class="active-label">Active:</span>
            {#if $activeConstitutionIds.length > 0}
                <span class="count-badge" in:scale={{duration: 200}}>
                    {$activeConstitutionIds.length}
                </span>
            {/if}
        </div>
        
        <div class="chips-container">
            {#if $activeConstitutionIds.length > 0}
                {#each $activeConstitutionIds as id, i}
                    {@const constitution = $availableConstitutions.find(c => c.id === id)}
                    <span 
                        class="chip" 
                        in:slide|local={{delay: i * 50, duration: 200}}
                        out:fade|local={{duration: 150}}
                    >
                        <span class="chip-name">{constitution?.name ?? id}</span>
                        <button 
                            class="remove-btn"
                            title="Remove" 
                            on:click={() => $activeConstitutionIds = $activeConstitutionIds.filter(activeId => activeId !== id)}
                        >
                            ×
                        </button>
                    </span>
                {/each}
            {:else}
                <span class="none-selected">None selected</span>
            {/if}
        </div>
    </div>
</div>

<style>
    .constitution-selector {
        display: flex;
        flex-direction: column;
        gap: var(--space-md);
    }
    
    .select-prompt {
        font-size: 0.9em;
        color: var(--text-secondary);
        margin-bottom: var(--space-xs);
    }
    
    .select-container {
        position: relative;
        box-shadow: var(--shadow-sm);
        border-radius: var(--radius-md);
        transition: all 0.2s ease;
    }
    
    .select-container:hover {
        box-shadow: var(--shadow-md);
    }
    
    .constitution-select {
        width: 100%;
        min-height: 100px;
        padding: var(--space-sm);
        background-color: var(--input-bg);
        color: var(--text-primary);
        border: 1px solid var(--input-border);
        border-radius: var(--radius-md);
        font-size: 0.9em;
        outline: none;
        transition: all 0.2s ease;
    }
    
    .constitution-select:focus {
        border-color: var(--primary-light);
        box-shadow: 0 0 0 2px rgba(157, 70, 255, 0.1);
    }
    
    .constitution-select option {
        padding: var(--space-sm);
        background-color: var(--bg-surface);
    }
    
    .selected-chips {
        display: flex;
        flex-direction: column;
        gap: var(--space-sm);
    }
    
    .chips-header {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
    }
    
    .active-label {
        font-weight: 600;
        color: var(--text-primary);
    }
    
    .count-badge {
        background-color: var(--primary-light);
        color: white;
        font-size: 0.75em;
        padding: 2px 6px;
        border-radius: var(--radius-pill);
        font-weight: bold;
    }
    
    .chips-container {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-sm);
        align-items: center;
        min-height: 30px;
    }
    
    .chip {
        background: linear-gradient(135deg, var(--primary-dark), var(--primary));
        color: white;
        padding: var(--space-xs) var(--space-sm);
        border-radius: var(--radius-pill);
        font-size: 0.85em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    
    .chip:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }
    
    .chip-name {
        max-width: 150px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .remove-btn {
        background: none;
        border: none;
        color: white;
        cursor: pointer;
        padding: 0;
        margin-left: 2px;
        font-weight: bold;
        font-size: 1.2em;
        line-height: 1;
        opacity: 0.8;
        transition: opacity 0.2s ease;
    }
    
    .remove-btn:hover {
        opacity: 1;
    }
    
    .none-selected {
        font-style: italic;
        font-size: 0.9em;
        color: var(--text-secondary);
    }
</style>

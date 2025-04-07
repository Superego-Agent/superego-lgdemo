<script lang="ts">
    import { availableConstitutions, compareSets } from '../stores';
    import { v4 as uuidv4 } from 'uuid'; // Need to install uuid: npm install uuid @types/uuid
    import { slide, fade, fly } from 'svelte/transition';

    function addCompareSet() {
        const newSet: CompareSet = {
            id: `set-${uuidv4().substring(0, 4)}`, // Short unique ID
            constitution_ids: [],
            name: `Set ${$compareSets.length + 1}` // Default name
        };
        compareSets.update(sets => [...sets, newSet]);
    }

    function removeCompareSet(setId: string) {
        compareSets.update(sets => sets.filter(s => s.id !== setId));
    }

    function addConstitutionToSet(setId: string, constitutionId: string) {
        if (!constitutionId) return; // Ignore empty selections
        compareSets.update(sets => {
            const setIndex = sets.findIndex(s => s.id === setId);
            if (setIndex > -1 && !sets[setIndex].constitution_ids.includes(constitutionId)) {
                sets[setIndex].constitution_ids = [...sets[setIndex].constitution_ids, constitutionId];
            }
            return sets;
        });
    }

    function removeConstitutionFromSet(setId: string, constitutionId: string) {
         compareSets.update(sets => {
            const setIndex = sets.findIndex(s => s.id === setId);
            if (setIndex > -1) {
                sets[setIndex].constitution_ids = sets[setIndex].constitution_ids.filter(id => id !== constitutionId);
            }
            return sets;
        });
    }
</script>

<div class="compare-interface">
    <button 
        on:click={addCompareSet} 
        class="add-set-button"
        in:fade={{duration: 200}}
    >
        <span class="button-icon">+</span> Add Comparison Set
    </button>

    {#if $compareSets.length === 0}
        <div class="no-sets-info" in:fade={{duration: 300}}>
            <p>Add sets to compare different constitution combinations.</p>
        </div>
    {/if}

    <div class="sets-container">
        {#each $compareSets as set, i (set.id)}
            <div 
                class="compare-set-card" 
                in:fly={{y: 20, delay: i * 100, duration: 300}}
                out:fade={{duration: 200}}
            >
                <div class="card-header">
                    <input 
                        type="text" 
                        bind:value={set.name} 
                        placeholder="Set Name" 
                        class="set-name-input"
                    />
                    <button 
                        class="remove-set-button" 
                        title="Remove Set" 
                        on:click={() => removeCompareSet(set.id)}
                    >
                        ×
                    </button>
                </div>

                <div class="constitution-adder">
                    <select 
                        on:change={(e) => addConstitutionToSet(set.id, (e.target as HTMLSelectElement).value)} 
                        title="Add a constitution to this set"
                        class="constitution-select"
                    >
                        <option value="">Add Constitution...</option>
                        {#each $availableConstitutions as constitution (constitution.id)}
                            {#if !set.constitution_ids.includes(constitution.id)}
                                <option value={constitution.id} title={constitution.description}>
                                    {constitution.name} ({constitution.id})
                                </option>
                            {/if}
                        {/each}
                    </select>
                </div>

                <div class="selected-chips">
                    {#if set.constitution_ids.length > 0}
                        {#each set.constitution_ids as id, i}
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
                                    on:click={() => removeConstitutionFromSet(set.id, id)}
                                >
                                    ×
                                </button>
                            </span>
                        {/each}
                    {:else}
                        <span class="empty-state">No constitutions added</span>
                    {/if}
                </div>
            </div>
        {/each}
    </div>
    
    <div class="info-note">
        <span class="info-icon">ℹ️</span>
        <p>An 'Inner Agent Only' run (no constitution) will always be included automatically in the comparison.</p>
    </div>
</div>

<style>
    .compare-interface {
        display: flex;
        flex-direction: column;
        gap: var(--space-md);
    }
    
    .add-set-button {
        width: 100%;
        padding: var(--space-sm) var(--space-md);
        margin-bottom: var(--space-sm);
        background-color: var(--secondary);
        color: white;
        border: none;
        border-radius: var(--radius-md);
        cursor: pointer;
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-xs);
        transition: all 0.3s ease;
        box-shadow: var(--shadow-sm);
    }
    
    .add-set-button:hover {
        background-color: var(--secondary-dark);
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    
    .button-icon {
        font-weight: bold;
        font-size: 1.2em;
    }
    
    .no-sets-info {
        background-color: var(--bg-elevated);
        border-radius: var(--radius-md);
        padding: var(--space-md);
        text-align: center;
        border: 1px solid var(--input-border);
    }
    
    .no-sets-info p {
        margin: 0;
        font-size: 0.9em;
        color: var(--text-secondary);
        font-style: italic;
    }
    
    .sets-container {
        display: flex;
        flex-direction: column;
        gap: var(--space-md);
    }
    
    .compare-set-card {
        border: 1px solid var(--input-border);
        border-radius: var(--radius-md);
        padding: var(--space-md);
        background-color: var(--bg-surface);
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    
    .compare-set-card:hover {
        box-shadow: var(--shadow-md);
    }
    
    .catyld-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--space-md);
        border-bottom: 1px solid var(--input-border);
        padding-bottom: var(--space-sm);
    }
    
    .set-name-input {
        border: none;
        font-weight: bold;
        font-size: 1em;
        flex-grow: 1;
        margin-right: var(--space-md);
        padding: var(--space-xs) 0;
        background-color: transparent;
        color: var(--text-primary);
    }
    
    .set-name-input:focus { 
        outline: none; 
        border-bottom: 1px solid var(--primary);
    }
    
    .remove-set-button {
        background: none;
        border: none;
        color: var(--error);
        font-size: 1.4em;
        cursor: pointer;
        line-height: 1;
        padding: 0;
        opacity: 0.8;
        transition: all 0.2s ease;
    }
    
    .remove-set-button:hover { 
        opacity: 1;
        transform: scale(1.1);
    }
    
    .constitution-adder {
        margin-bottom: var(--space-md);
    }
    
    .constitution-select {
        width: 100%;
        padding: var(--space-sm);
        border: 1px solid var(--input-border);
        border-radius: var(--radius-sm);
        font-size: 0.9em;
        background-color: var(--input-bg);
        color: var(--text-primary);
        transition: all 0.2s ease;
    }
    
    .constitution-select:focus {
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
    }
    
    .selected-chips {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-sm);
        align-items: center;
        min-height: 36px;
    }
    
    .chip {
        background-color: var(--input-bg);
        color: var(--text-primary);
        padding: var(--space-xs) var(--space-sm);
        border-radius: var(--radius-pill);
        border: 1px solid var(--input-border);
        font-size: 0.85em;
        display: inline-flex;
        align-items: center;
        gap: var(--space-xs);
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    
    .chip:hover {
        transform: translateY(-1px);
        background-color: var(--bg-elevated);
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
        color: var(--text-secondary);
        cursor: pointer;
        padding: 0;
        font-weight: bold;
        font-size: 1.2em;
        line-height: 1;
        opacity: 0.8;
        transition: opacity 0.2s ease;
    }
    
    .remove-btn:hover {
        opacity: 1;
    }
    
    .empty-state {
        font-style: italic;
        font-size: 0.85em;
        color: var(--text-secondary);
    }
    
    .info-note {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        margin-top: var(--space-sm);
        padding: var(--space-md);
        background-color: var(--bg-elevated);
        border-radius: var(--radius-md);
        border: 1px solid var(--input-border);
        box-shadow: var(--shadow-sm);
    }
    
    .info-note p {
        margin: 0;
        font-size: 0.8em;
        color: var(--text-secondary);
    }
    
    .info-icon {
        font-size: 1em;
    }
</style>

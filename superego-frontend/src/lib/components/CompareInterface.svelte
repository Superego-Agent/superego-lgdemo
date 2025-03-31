<script lang="ts">
    import { availableConstitutions, compareSets } from '../stores';
    import { v4 as uuidv4 } from 'uuid'; // Need to install uuid: npm install uuid @types/uuid

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
    <button on:click={addCompareSet} class="add-set-button"> + Add Comparison Set </button>

    {#if $compareSets.length === 0}
        <p class="no-sets-info">Add sets to compare different constitution combinations.</p>
    {/if}

    <div class="sets-container">
        {#each $compareSets as set (set.id)}
            <div class="compare-set-card">
                <div class="card-header">
                    <input type="text" bind:value={set.name} placeholder="Set Name" class="set-name-input"/>
                     <button class="remove-set-button" title="Remove Set" on:click={() => removeCompareSet(set.id)}>
                         &times;
                     </button>
                </div>

                <div class="constitution-adder">
                     <select on:change={(e) => addConstitutionToSet(set.id, (e.target as HTMLSelectElement).value)} title="Add a constitution to this set">
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
                    {#each set.constitution_ids as id}
                        {@const constitution = $availableConstitutions.find(c => c.id === id)}
                        <span class="chip">
                            {constitution?.name ?? id}
                            <button title="Remove" on:click={() => removeConstitutionFromSet(set.id, id)}>
                                &times;
                            </button>
                        </span>
                    {:else}
                         <span style="font-style: italic; font-size: 0.8em; color: #777;">No constitutions added</span>
                    {/each}
                </div>

            </div>
        {/each}
    </div>
     <p style="font-size: 0.8em; color: #666; margin-top: 15px;">Note: An 'Inner Agent Only' run (no constitution) will always be included automatically in the comparison.</p>
</div>

<style>
    .compare-interface {
        /* Styles for the compare mode section */
    }
    .add-set-button {
        width: 100%;
        padding: 8px 12px;
        margin-bottom: 15px;
        background-color: #17a2b8;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    .add-set-button:hover {
        background-color: #138496;
    }
    .no-sets-info {
        font-size: 0.9em;
        color: #666;
        font-style: italic;
        text-align: center;
        margin-bottom: 15px;
    }
    .sets-container {
        display: flex;
        flex-direction: column;
        gap: 15px;
    }
    .compare-set-card {
        border: 1px solid #ccc;
        border-radius: 6px;
        padding: 10px 15px;
        background-color: #fff;
    }
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        border-bottom: 1px solid #eee;
        padding-bottom: 5px;
    }
    .set-name-input {
        border: none;
        font-weight: bold;
        font-size: 1em;
        flex-grow: 1;
        margin-right: 10px;
        padding: 2px 0; /* Minimal padding */
    }
    .set-name-input:focus { outline: none; border-bottom: 1px solid #007bff;}

    .remove-set-button {
        background: none;
        border: none;
        color: #dc3545;
        font-size: 1.4em;
        cursor: pointer;
        line-height: 1;
        padding: 0;
    }
    .remove-set-button:hover { color: #a71d2a; }

    .constitution-adder select {
        width: 100%;
        padding: 5px 8px;
        margin-bottom: 10px;
        border: 1px solid #ccc;
        border-radius: 4px;
        font-size: 0.9em;
    }

    /* Reusing chip styles from ConstitutionDropdown */
     .selected-chips {
        /* margin-top: 10px; */ /* Already styled above? Check hierarchy */
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        align-items: center;
        min-height: 20px; /* Ensure space even when empty */
    }
    .chip {
        background-color: #d1e7ff;
        color: #0d6efd;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.85em;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }
    .chip button {
        background: none;
        border: none;
        color: #0d6efd;
        cursor: pointer;
        padding: 0;
        margin-left: 2px;
        font-weight: bold;
        line-height: 1;
    }
     .chip button:hover {
         color: #0a58ca;
     }

</style>
<script lang="ts">
    import { availableConstitutions, activeConstitutionIds } from '../stores';
    import { tick } from 'svelte';

    let selectedIds: string[] = $activeConstitutionIds; // Initialize with current selection

    // Update the store whenever the local selection changes
    $: {
        // Ensure 'none' is present if the selection is empty, otherwise remove 'none' if others are selected.
        const finalSelection = selectedIds.filter(id => id !== 'none');
        if (finalSelection.length === 0) {
            $activeConstitutionIds = ['none'];
        } else {
            $activeConstitutionIds = finalSelection;
        }
        // console.log('Active Constitution IDs:', $activeConstitutionIds); // For debugging
    }

    // Filter out the 'none' constitution from the display options if it exists
    $: displayConstitutions = $availableConstitutions.filter(c => c.id !== 'none');

</script>

<div class="constitution-selector">
    {#if displayConstitutions.length > 0}
        <fieldset>
            <legend>Active Constitution(s)</legend>
            <div class="options-wrapper">
                {#each displayConstitutions as constitution (constitution.id)}
                    <label class="option">
                        <input
                            type="checkbox"
                            bind:group={selectedIds}
                            value={constitution.id}
                        />
                        <span title={constitution.description || constitution.name}>
                            {constitution.name}
                        </span>
                    </label>
                {/each}
            </div>
        </fieldset>
    {:else}
        <p class="loading-text">Loading constitutions...</p>
        {/if}
</div>

<style>
    .constitution-selector {
        padding: var(--space-sm) 0; /* Add some vertical padding */
        font-size: 0.9em;
         /* Max height and scroll for many constitutions */
        max-height: 150px; /* Adjust as needed */
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: var(--primary-light) var(--bg-surface);
    }
    .constitution-selector::-webkit-scrollbar { width: 6px; }
    .constitution-selector::-webkit-scrollbar-track { background: var(--bg-surface); }
    .constitution-selector::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }

    fieldset {
        border: 1px solid var(--input-border);
        border-radius: var(--radius-md);
        padding: var(--space-sm) var(--space-md);
        margin: 0;
    }

    legend {
        padding: 0 var(--space-sm);
        font-weight: bold;
        color: var(--text-secondary);
        font-size: 0.8em;
    }

    .options-wrapper {
        display: flex;
        flex-direction: column; /* Stack checkboxes */
        gap: var(--space-xs);
    }

    .option {
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        cursor: pointer;
        padding: var(--space-xs) 0;
        transition: color 0.2s ease;
    }
    .option:hover {
        color: var(--primary);
    }

    .option input[type="checkbox"] {
        cursor: pointer;
        accent-color: var(--primary); /* Style the checkbox color */
    }

     .option span {
         /* Prevent text wrapping */
         white-space: nowrap;
         overflow: hidden;
         text-overflow: ellipsis;
     }

    .loading-text {
        font-style: italic;
        color: var(--text-secondary);
        padding: var(--space-md);
        text-align: center;
    }
</style>
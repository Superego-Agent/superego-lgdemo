<script lang="ts">
    import { availableConstitutions, activeConstitutionIds } from '../stores';

    // TODO: Implement dropdown selection logic
    // Maybe use a multi-select library or build custom one?
    // For now, just display available and selected.

</script>

<div class="constitution-selector use-mode">
    <p style="font-size: 0.9em; color: #666;">Select constitutions to apply:</p>

    <select multiple bind:value={$activeConstitutionIds} style="width: 100%; min-height: 80px;">
        {#each $availableConstitutions as constitution (constitution.id)}
            <option value={constitution.id} title={constitution.description}>
                {constitution.name} ({constitution.id})
            </option>
        {/each}
    </select>

    <div class="selected-chips">
        <strong>Active:</strong>
        {#if $activeConstitutionIds.length > 0}
            {#each $activeConstitutionIds as id}
                {@const constitution = $availableConstitutions.find(c => c.id === id)}
                <span class="chip">
                    {constitution?.name ?? id}
                    <button title="Remove" on:click={() => $activeConstitutionIds = $activeConstitutionIds.filter(activeId => activeId !== id)}>
                        &times;
                    </button>
                </span>
            {/each}
        {:else}
            <span style="font-style: italic; font-size: 0.9em;">None selected</span>
        {/if}
    </div>
</div>

<style>
    .constitution-selector {
        /* Styles specific to this component */
    }
    .selected-chips {
        margin-top: 10px;
        display: flex;
        flex-wrap: wrap;
        gap: 5px;
        align-items: center;
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
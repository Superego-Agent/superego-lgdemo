<script lang="ts">
import { localConstitutionsStore } from '../localConstitutions';
import { globalConstitutions, isLoadingGlobalConstitutions, globalConstitutionsError } from '../stores/globalConstitutionsStore'; 
import { createEventDispatcher } from 'svelte';
import IconInfo from '~icons/fluent/info-24-regular';
import IconChevronDown from '~icons/fluent/chevron-down-24-regular';
import IconChevronUp from '~icons/fluent/chevron-up-24-regular';
import IconAdd from '~icons/fluent/add-24-regular';
import ConstitutionInfoModal from './ConstitutionInfoModal.svelte';
import AddConstitutionModal from './AddConstitutionModal.svelte';
import { fetchConstitutionContent } from '../api'; 

const dispatch = createEventDispatcher();

let isExpanded = true; // Start expanded
let selectedLevels: Record<string, number> = {}; 

let showModal = false;
let modalIsLoading = false;
let modalError: string | null = null;
let modalTitle: string = '';
let modalDescription: string | undefined = undefined;
let modalContent: string | undefined = undefined;
let showAddModal = false;

// Function to handle checkbox changes (uses ID, works for both global and local)
function handleCheckChange(id: string, isChecked: boolean) {
    if (isChecked) {
        selectedLevels[id] = 3;
    } else {
        delete selectedLevels[id];
    }
    selectedLevels = { ...selectedLevels }; // Trigger reactivity
}

// Function to show the info modal - accepts the combined type
async function showInfo(item: ConstitutionItem | LocalConstitution) { // Simplified type
    modalTitle = item.title;
    // Determine if it's global (has description) or local (has text)
    const isGlobal = 'description' in item;
    modalDescription = isGlobal ? item.description : `Local constitution created ${new Date((item as LocalConstitution).createdAt).toLocaleDateString()}`;
    modalContent = undefined;
    modalError = null;
    modalIsLoading = true;
    showModal = true;

    if (!isGlobal) {
        modalContent = (item as LocalConstitution).text;
        modalIsLoading = false;
    } else {
        // For global, fetch content
        try {
            modalContent = await fetchConstitutionContent(item.id);
        } catch (err: any) {
            console.error("Failed to fetch constitution content:", err);
            modalError = err.message || "Unknown error fetching content.";
        } finally {
            modalIsLoading = false;
        }
    }
}

function toggleExpand() {
    isExpanded = !isExpanded;
}


// --- Derive configuredModules and dispatch changes ---
let configuredModules: ConfiguredConstitutionModule[] = [];
$: {
    configuredModules = Object.entries(selectedLevels)
        .map(([id, level]): ConfiguredConstitutionModule | null => {
            // Find title from either global or local store
            const globalItem = $globalConstitutions.find((c: ConstitutionItem) => c.id === id);
            const localItem = $localConstitutionsStore.find((c: LocalConstitution) => c.id === id);
            const title = globalItem?.title ?? localItem?.title;
            return title ? { id, title: title, adherence_level: level } : null;
        })
        .filter((module): module is ConfiguredConstitutionModule => module !== null);
    dispatch('configChange', configuredModules);
}

</script>

<div class="selector-card">
    <!-- Header with integrated toggle -->
    <div class="selector-header" on:click={toggleExpand} role="button" tabindex="0" on:keydown={(e) => e.key === 'Enter' && toggleExpand()}>
        <span class="header-title">Constitutions</span>
        {#if isExpanded}
            <IconChevronDown class="toggle-icon"/>
        {:else}
            <IconChevronUp class="toggle-icon"/>
        {/if}
    </div>

    <!-- Collapsible content area -->
    {#if isExpanded}
        <div class="options-container">
            {#if $isLoadingGlobalConstitutions}
                <p class="loading-text">Loading global constitutions...</p>
            {:else if $globalConstitutionsError}
                <p class="loading-text error-text">Error loading: {$globalConstitutionsError}</p>
            {:else}
                <div class="options-wrapper">
                     <div class="option-item add-item" on:click={() => showAddModal = true} role="button" tabindex="0" on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') showAddModal = true; }}>
                         <div class="option-label add-label">
                             <IconAdd class="add-icon"/>
                             <span class="title-text">Add Local Constitution</span>
                         </div>
                     </div>

                     {#if $globalConstitutions.length > 0}
                         <h4 class="list-heading">Global</h4>
                         {#each $globalConstitutions as item (item.id)}
                             {@const isSelected = selectedLevels[item.id] !== undefined}
                             <div class="option-item">
                                 <label class="option-label">
                                     <input type="checkbox" checked={isSelected} on:change={(e) => handleCheckChange(item.id, e.currentTarget.checked)} />
                                     <span class="title-text" title={item.description}>{item.title}</span>
                                     <button class="info-button" title="Show constitution info" on:click|stopPropagation={() => showInfo(item)}><IconInfo /></button>
                                 </label>
                                 {#if isSelected}
                                     <div class="slider-container">
                                         <input type="range" min="1" max="5" step="1" bind:value={selectedLevels[item.id]} class="adherence-slider" aria-label="{item.title} Adherence Level" />
                                         <span class="level-display">{selectedLevels[item.id]}/5</span>
                                     </div>
                                 {/if}
                             </div>
                         {/each}
                     {/if}

                     {#if $localConstitutionsStore.length > 0}
                         <h4 class="list-heading">Local</h4>
                         {#each $localConstitutionsStore as item (item.id)}
                             {@const isSelected = selectedLevels[item.id] !== undefined}
                             <div class="option-item">
                                 <label class="option-label">
                                     <input type="checkbox" checked={isSelected} on:change={(e) => handleCheckChange(item.id, e.currentTarget.checked)} />
                                     <span class="title-text"><span class="local-indicator">[Local]</span>{item.title}</span>
                                     <button class="info-button" title="Show constitution info" on:click|stopPropagation={() => showInfo(item)}><IconInfo /></button>
                                 </label>
                                 {#if isSelected}
                                     <div class="slider-container">
                                         <input type="range" min="1" max="5" step="1" bind:value={selectedLevels[item.id]} class="adherence-slider" aria-label="{item.title} Adherence Level" />
                                         <span class="level-display">{selectedLevels[item.id]}/5</span>
                                     </div>
                                 {/if}
                             </div>
                         {/each}
                     {/if}

                     {#if $globalConstitutions.length === 0 && $localConstitutionsStore.length === 0}
                          <p class="loading-text">No constitutions available.</p>
                     {/if}
                </div>
            {/if}
        </div>
    {/if}
</div>

{#if showModal}
    <ConstitutionInfoModal
        title={modalTitle}
        description={modalDescription}
        content={modalContent}
        isLoading={modalIsLoading}
        error={modalError}
        on:close={() => showModal = false}
    />
{/if}

{#if showAddModal}
    <AddConstitutionModal on:close={() => showAddModal = false} />
{/if}

<style lang="scss">
    @use '../styles/mixins' as *;

    /* Remove fieldset and legend styles */

    .selector-card {
        @include base-card(); // Use mixin
        overflow: hidden; // Keep specific overflow
        margin-bottom: var(--space-sm); // Keep specific margin
        transition: box-shadow 0.2s ease; // Keep specific transition

        &:hover { // Keep hover effect separate if not in mixin
             box-shadow: var(--shadow-md);
        }
    }

    .selector-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: var(--space-sm) var(--space-md);
        cursor: pointer;
        border-bottom: 1px solid var(--input-border); /* Separator when expanded */
        background-color: var(--bg-elevated); /* Slightly different header bg */
        transition: background-color 0.2s ease;
    }
    .selector-header:hover {
        background-color: var(--primary-lightest);
    }

    .header-title {
        font-weight: 600; /* Make header title bolder */
        font-size: 0.9em;
        color: var(--text-primary);
    }

    .toggle-icon {
        color: var(--text-secondary);
        transition: transform 0.2s ease-in-out;
    }

    .options-container {
        padding: var(--space-sm) var(--space-md);
        max-height: 350px; /* Further increased height */
        overflow-y: auto;
        @include custom-scrollbar($track-bg: var(--bg-surface), $thumb-bg: var(--primary-light), $width: 6px); // Use mixin
    }
    
    // Scrollbar styles handled by mixin above

    .options-wrapper {
        display: flex;
        flex-direction: column;
        gap: var(--space-xs);
    }

    .option-item {
        display: grid;
        grid-template-columns: minmax(150px, 3fr) minmax(100px, 1fr);
        gap: var(--space-xs) var(--space-md);
        align-items: center;
        padding: var(--space-xs); /* Add padding for hover effect */
        border-radius: var(--radius-sm); /* Rounded corners for hover */
        transition: background-color 0.15s ease; /* Smooth hover transition */
    }
    .option-item:hover {
         background-color: var(--primary-lightest); /* Hover background color */
    }

    .option-label {
        grid-column: 1 / 2;
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        cursor: pointer;
        transition: color 0.2s ease;
        overflow: hidden; /* Let the container handle overflow */
    }
    .option-label:hover .title-text { /* Target title text on hover */
        color: var(--primary);
    }
    .option-label input[type="checkbox"] {
        cursor: pointer;
        accent-color: var(--primary);
        flex-shrink: 0;
    }
    .title-text {
        /* Allow title to take space but truncate */
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex-grow: 1; /* Allow text to grow */
        margin-right: var(--space-xs);
    }
    .info-button {
        @include icon-button($padding: 0); // Use mixin, override padding
        flex-shrink: 0; // Keep specific flex-shrink
        opacity: 0.6; // Keep specific initial opacity

        &:hover { // Keep specific hover styles (only color/opacity change)
            color: var(--primary);
            opacity: 1;
            background-color: transparent; // Prevent mixin hover background
        }
    }
    
    /* Add constitution item styles */
    .add-item {
        cursor: pointer;
        grid-template-columns: 1fr; /* Use a single column for the add item */
    }
    
    .add-label {
        grid-column: 1 / -1;
        color: var(--primary);
    }
    
    .add-icon {
        font-size: 1.2em;
        font-weight: bold;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 16px;
        line-height: 1;
    }

    .slider-container {
        grid-column: 2 / 3;
        display: flex;
        align-items: center;
        gap: var(--space-sm);
        /* min-width: 100px; */
    }

    .adherence-slider {
        flex-grow: 1; /* Allow slider to take available space */
        cursor: pointer;
        accent-color: var(--primary);
        height: 8px; /* Make slider visually smaller */
    }

    .level-display {
        font-size: 0.8em;
        color: var(--text-secondary);
        min-width: 25px; /* Ensure space for "X/5" */
        text-align: right;
    }

    .loading-text {
        font-style: italic;
        color: var(--text-secondary);
        padding: var(--space-md);
        text-align: center;
    }

    .local-indicator {
        font-weight: 600;
        color: var(--secondary); /* Or another distinct color */
        margin-right: var(--space-xs);
        font-size: 0.9em;
    }
</style>

<script lang="ts">
    import { availableConstitutions, constitutionAdherenceLevels } from '../stores';
    import { tick } from 'svelte';
    // import { fly } from 'svelte/transition'; // Removed fly import
    import IconInfo from '~icons/fluent/info-24-regular';
    import IconChevronDown from '~icons/fluent/chevron-down-24-regular'; // Icon for toggle
    import IconChevronUp from '~icons/fluent/chevron-up-24-regular'; // Icon for toggle
    import ConstitutionInfoModal from './ConstitutionInfoModal.svelte';
    import { fetchConstitutionContent } from '../api';

    // Component State
    let isExpanded = true; // Start expanded

    // Modal State
    let showModal = false;
    let modalIsLoading = false;
    let modalError: string | null = null;
    let modalTitle: string = '';
    let modalDescription: string | undefined = undefined;
    let modalContent: string | undefined = undefined;

    // Filter out the 'none' constitution from the display options if it exists
    // Use constitution.title now
    $: displayConstitutions = $availableConstitutions.filter(c => c.id !== 'none');

    // Function to handle checkbox changes
    function handleCheckChange(id: string, isChecked: boolean) {
        if (isChecked) {
            // Add constitution with default level 3 if checked
            $constitutionAdherenceLevels[id] = 3;
            // Trigger store update
            constitutionAdherenceLevels.set($constitutionAdherenceLevels);
        } else {
            // Remove constitution if unchecked
            delete $constitutionAdherenceLevels[id];
            // Trigger store update
            constitutionAdherenceLevels.set($constitutionAdherenceLevels);
        }
        // console.log('Adherence Levels:', $constitutionAdherenceLevels); // For debugging
    }

    // Reactive statement to ensure 'none' is represented if no constitutions are selected
    // This replaces the old activeConstitutionIds logic
    $: {
        const activeIds = Object.keys($constitutionAdherenceLevels);
        // If you still need activeConstitutionIds store for other parts, update it here.
        // Otherwise, this block might only be needed if 'none' representation is critical elsewhere.
        // For now, we assume the primary state is constitutionAdherenceLevels.
        // Example: activeConstitutionIds.set(activeIds.length > 0 ? activeIds : ['none']);
    }

    // Function to show the info modal
    async function showInfo(constitution: ConstitutionItem) {
        modalTitle = constitution.title;
        modalDescription = constitution.description;
        modalContent = undefined; // Clear previous content
        modalError = null; // Clear previous error
        modalIsLoading = true;
        showModal = true;

        try {
            modalContent = await fetchConstitutionContent(constitution.id);
        } catch (err: any) {
            console.error("Failed to fetch constitution content:", err);
            modalError = err.message || "Unknown error fetching content.";
        } finally {
            modalIsLoading = false;
        }
    }

    function toggleExpand() {
        isExpanded = !isExpanded;
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
            {#if displayConstitutions.length > 0}
                <div class="options-wrapper">
                        {#each displayConstitutions as constitution (constitution.id)}
                            <div class="option-item">
                                <label class="option-label">
                                    <input
                                type="checkbox"
                                checked={$constitutionAdherenceLevels[constitution.id] !== undefined}
                                on:change={(e) => handleCheckChange(constitution.id, e.currentTarget.checked)}
                            />
                            <span class="title-text" title={constitution.description || constitution.title}>
                                {constitution.title}
                            </span>
                            <button class="info-button" title="Show constitution info" on:click|stopPropagation={() => showInfo(constitution)}>
                                <IconInfo />
                            </button>
                        </label>
                        {#if $constitutionAdherenceLevels[constitution.id] !== undefined}
                            <div class="slider-container">
                                <input
                                    type="range"
                                    min="1"
                                    max="5"
                                    step="1"
                                    bind:value={$constitutionAdherenceLevels[constitution.id]}
                                    class="adherence-slider"
                                    aria-label="{constitution.title} Adherence Level"
                                />
                                <span class="level-display">
                                    {$constitutionAdherenceLevels[constitution.id]}/5
                                </span>
                                        <!-- Info button removed from here -->
                                    </div>
                                {/if}
                            </div>
                        {/each}
                    </div>
                {:else}
                    <p class="loading-text">Loading constitutions...</p>
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

<style>
    /* Remove fieldset and legend styles */

    .selector-card {
        background-color: var(--bg-surface); /* Card background */
        border: 1px solid var(--input-border);
        border-radius: var(--radius-lg); /* Rounded corners */
        overflow: hidden; /* Clip content during transition */
        margin-bottom: var(--space-sm); /* Space below card */
        box-shadow: var(--shadow-sm);
        transition: box-shadow 0.2s ease;
    }
    .selector-card:hover {
         box-shadow: var(--shadow-md);
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
    .toggle-icon.rotated {
        transform: rotate(180deg);
    }

    .options-container {
        padding: var(--space-sm) var(--space-md);
        max-height: 250px; /* Increased default height */
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: var(--primary-light) var(--bg-surface);
    }
    .options-container::-webkit-scrollbar { width: 6px; }
    .options-container::-webkit-scrollbar-track { background: var(--bg-surface); }
    .options-container::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }

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
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        color: var(--text-secondary);
        cursor: pointer;
        display: flex; /* Align icon nicely */
        align-items: center;
        justify-content: center;
        flex-shrink: 0; /* Prevent button from shrinking */
        opacity: 0.6;
        transition: opacity 0.2s ease, color 0.2s ease;
    }
    .info-button:hover {
        color: var(--primary);
        opacity: 1;
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
</style>

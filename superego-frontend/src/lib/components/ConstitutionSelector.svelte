<script lang="ts">
    import { availableConstitutions, constitutionAdherenceLevels } from '../stores';
    import { tick } from 'svelte';
    import IconInfo from '~icons/fluent/info-24-regular';
    import ConstitutionInfoModal from './ConstitutionInfoModal.svelte'; // Import the modal
    import { fetchConstitutionContent } from '../api'; // Import the API function

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

</script>

<div class="constitution-selector">
    {#if displayConstitutions.length > 0}
        <fieldset>
            <legend>Constitution Adherence</legend>
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
                             <!-- Info button now calls showInfo -->
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
        </fieldset>
    {:else}
        <p class="loading-text">Loading constitutions...</p>
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

    .option-item {
        display: grid;
        /* Adjust grid: Give label column more space (e.g., 3fr) vs slider (1fr) */
        grid-template-columns: minmax(150px, 3fr) minmax(100px, 1fr);
        gap: var(--space-xs) var(--space-md); /* Row gap | Column gap */
        align-items: center;
        padding: var(--space-xs) 0;
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
        margin-right: var(--space-xs); /* Restore space before info button */
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

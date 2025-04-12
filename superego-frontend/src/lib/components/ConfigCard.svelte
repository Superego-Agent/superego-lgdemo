<script lang="ts">
    import { fetchConstitutionContent } from '$lib/api/rest.svelte';
    import { localConstitutionsStore } from '$lib/state/constitutions.svelte';
    import ConstitutionInfoModal from './ConstitutionInfoModal.svelte';

    // --- Component Props ---
    interface Props {
        threadId: string;
        config: ThreadConfigState; 
        isActive?: boolean;
        onSelect?: (detail: { threadId: string }) => void;
        onToggle?: (detail: { isEnabled: boolean }) => void;
    }
    let { threadId, config, isActive = false, onSelect = () => {}, onToggle = () => {} }: Props = $props();

    // --- Event Dispatcher ---

    // --- Modal State ---
    let showModal = $state(false);
    let modalIsLoading = $state(false);
    let modalError: string | null = $state(null);
    let modalTitle: string = $state("");
    let modalDescription: string | undefined = $state(undefined);
    let modalContent: string | undefined = $state(undefined);

    // --- Chip Display Logic ---
    const MAX_VISIBLE_CHIPS = 4; // Show 4 chips initially
    let allModules = $derived(config.runConfig?.configuredModules ?? []);
    let visibleChips = $derived(allModules.slice(0, MAX_VISIBLE_CHIPS));
    let hiddenChipCount = $derived(allModules.length - visibleChips.length);

    // --- Event Handlers ---
    function handleCardClick() {
        // Select the entire configuration when the card background is clicked
        onSelect({ threadId });
    }

    function handleToggleClick() {
        // Only handle the toggle action, prevent card selection
        const newIsEnabled = !config.isEnabled;
        onToggle({ isEnabled: newIsEnabled });
    }

    async function showConstitutionInfo(moduleId: string, moduleTitle: string) {
        // Prevent card selection when a chip is clicked
        // stopPropagation is handled inline in the template for chip clicks

        modalTitle = moduleTitle;
        modalContent = undefined;
        modalError = null;
        modalIsLoading = true;
        showModal = true;

        // Try finding local constitution first
        const localItem = localConstitutionsStore.localConstitutions.find(c => c.id === moduleId);

        if (localItem) {
            modalDescription = `Local constitution created ${new Date(localItem.createdAt).toLocaleDateString()}`;
            modalContent = localItem.text;
            modalIsLoading = false;
        } else {
            // Assume it's a global constitution if not found locally
            // We might need a more robust way to get the description if needed,
            // but for now, we'll fetch content.
            modalDescription = "Global Constitution"; 
            try {
                modalContent = await fetchConstitutionContent(moduleId);
            } catch (err: any) {
                console.error("Failed to fetch constitution content:", err);
                modalError = err.message || "Unknown error fetching content.";
            } finally {
                modalIsLoading = false;
            }
        }
    }

</script>

<!-- Main Card Div (acts like a button) -->
<div
    class="config-card"
    class:active={isActive}
    class:disabled={!config.isEnabled}
    onclick={handleCardClick}
    onkeydown={(e) => e.key === 'Enter' && handleCardClick()}
    role="button"
    tabindex="0"
    title={`Select configuration: ${config.name}`}
>
    <!-- Top Row: Name and Toggle -->
    <div class="card-top-row">
        <span class="config-name">{config.name}</span>
        <!-- Toggle Switch -->
        <label class="toggle-switch" title={config.isEnabled ? 'Disable Configuration' : 'Enable Configuration'}>
            <input
                type="checkbox"
                checked={config.isEnabled}
                onchange={e=>{e.stopPropagation();handleToggleClick()}}
            />
            <span class="slider"></span>
        </label>
    </div>

    <!-- Bottom Area: Constitution Chips -->
    {#if config.runConfig?.configuredModules && config.runConfig.configuredModules.length > 0}
        <div class="chips-container">
            {#each visibleChips as module (module.id)}
                 <button
                    class="chip"
                    onclick={e=>{e.stopPropagation(); showConstitutionInfo(module.id, module.title)}}
                    title={`View details for: ${module.title}`}
                >
                    {module.title}
                </button>
            {/each}
            {#if hiddenChipCount > 0}
                <div class="chip indicator-chip" title={`${hiddenChipCount} more constitutions`}>
                    +{hiddenChipCount}
                </div>
            {/if}
        </div>
    {/if}
</div>

<!-- Modal -->
{#if showModal}
  <ConstitutionInfoModal
    title={modalTitle}
    description={modalDescription}
    content={modalContent}
    isLoading={modalIsLoading}
    error={modalError}
    onClose={() => (showModal = false)}
  />
{/if}


<style lang="scss">
    @use "../styles/mixins" as *; // Import mixins
    @use "../styles/mixins" as *; // Assuming mixins are available

    .config-card {
        padding: var(--space-sm);
        border: 1px solid var(--primary-light); // Use primary-light for visibility
        border-radius: var(--radius-md);
        background-color: var(--bg-secondary);
        cursor: pointer;
        transition: all 0.2s ease-in-out;
        display: flex;
        flex-direction: column; // Stack top row and chips vertically
        gap: var(--space-sm); // Space between top row and chips
        min-width: 150px; // Ensure a minimum width
        width: 100%;
        max-width: 100%; // Prevent card from overflowing its container if container is constrained
        position: relative; // For potential absolute positioning if needed later

        &:hover {
            border-color: var(--primary-light);
            background-color: var(--bg-hover);
        }

        &.active {
            border-color: var(--primary);
            background-color: var(--primary-bg-subtle);
            box-shadow: 0 0 0 2px var(--primary-light);
            color: var(--primary); // Apply primary color to text when active
        }
    }

    .config-card.disabled {
        opacity: 0.6;
        cursor: not-allowed;
        // Optionally dim the background further or add other visual cues
        // background-color: var(--grey-lightest); // Example
    }

    .card-top-row {
        display: flex;
        justify-content: space-between; // Pushes name left, toggle right
        align-items: center;
        gap: var(--space-sm);
        width: 100%; // Ensure it takes full width
    }

    .config-name {
        font-weight: 600; // Make name slightly bolder
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        flex-grow: 1; // Allow name to take available space
        margin-right: var(--space-sm); // Ensure space before toggle
    }

    // --- Toggle Switch Styles ---
    .toggle-switch {
        position: relative;
        display: inline-block;
        width: 34px; // Smaller toggle
        height: 20px;
        flex-shrink: 0; // Prevent shrinking
        cursor: pointer;

        input {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: var(--grey-light, #ccc); // Use grey-light or fallback grey for off state
            transition: .3s;
            border-radius: 20px; // Fully rounded ends

            &:before {
                position: absolute;
                content: "";
                height: 14px; // Smaller circle
                width: 14px;
                left: 3px;
                bottom: 3px;
                background-color: var(--bg-surface); // Use theme variable instead of white
                transition: .3s;
                border-radius: 50%;
            }
        }

        input:checked + .slider {
            background-color: var(--primary); // On state color
        }

        input:focus + .slider {
            box-shadow: 0 0 1px var(--primary);
        }

        input:checked + .slider:before {
            transform: translateX(14px); // Move circle to the right
        }
    }

    // --- Chips Styles ---
    .chips-container {
        display: flex;
        flex-wrap: wrap;
        gap: var(--space-xs);
        width: 100%; // Take full width
        margin-top: var(--space-xs); // Ensure separation even without border if no chips
        // Removed max-height, overflow-y, and scrollbar styles

    .chip {
        /* @include small-button-reset(); // Commenting out as it might not exist or be needed */
        all: unset; // Basic button reset
        box-sizing: border-box; // Include padding and border in the element's total width and height
        padding: 2px 5px;
        background-color: var(--bg-surface); // Slightly different bg for chips
        border: 1px solid var(--primary-light);
        border-radius: var(--radius-lg); // More rounded chips

        font-size: 0.8em;
        color: var(--text-secondary);
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap; // Keep nowrap for ellipsis
        overflow: hidden; // Hide overflow
        text-overflow: ellipsis; // Add ellipsis for long text
        display: inline-block; // Needed for text-overflow on inline-like elements
        min-width: 50px; // Sensible minimum width
        flex-shrink: 1; // Allow chips to shrink if needed, but respect min-width

        &:hover {
            border-color: var(--primary);
            color: var(--primary);
            background-color: var(--primary-bg-subtle);
        }
    } // End of .chip rule

    .indicator-chip {
        // Similar base styles to .chip, but non-interactive appearance
        padding: 2px 5px;
        background-color: var(--bg-surface);
        border: 1px dashed var(--border-color); // Dashed border to indicate it's different
        border-radius: var(--radius-lg);
        font-size: 0.8em;
        color: var(--text-secondary);
        font-style: italic;
        cursor: default; // Not clickable
        white-space: nowrap;
    }
    }
</style>
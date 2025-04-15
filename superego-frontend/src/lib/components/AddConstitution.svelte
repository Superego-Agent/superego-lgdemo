<script lang="ts">

    import { fetchConstitutionContent, submitConstitution } from '$lib/api/rest.svelte';
    import { constitutionStore } from '$lib/state/constitutions.svelte'; // Updated import
    import { tick } from 'svelte';

    let { onConstitutionAdded = (detail?: { success: boolean }) => {}, onClose = () => {} } = $props<{
        onConstitutionAdded?: (detail?: { success: boolean }) => void;
        onClose?: () => void;
    }>();

    // Use the single store instance for global state
    let availableConstitutions = $derived(constitutionStore.globalHierarchy);
    let isLoading = $derived(constitutionStore.isLoadingGlobal);
    let error = $derived(constitutionStore.globalError);

    // --- Component State ---
    let constitutionTitle = $state('');
    let constitutionText = $state('');
    let submitForReview = $state(false); // Replaces isPrivate, default false
    let selectedTemplateId: string | null = $state(null);

    // Submission & Loading State
    let isSubmitting = $state(false);
    let submitStatus: { success?: boolean; message?: string } | null = $state(null);
    let templateLoading = $state(false);

    // --- Template Handling ---
    // Combine global and local for template dropdown
    type TemplateOption =
        | { type: 'remote'; id: string; title: string } // 'id' will be relativePath
        | { type: 'local'; id: string; title: string; text: string }; // 'id' will be localStorageKey



    // --- Functions ---
    function flattenHierarchy(hierarchy: ConstitutionHierarchy | null): RemoteConstitutionMetadata[] {
        if (!hierarchy) {
            return [];
        }
        const constitutions: RemoteConstitutionMetadata[] = [...hierarchy.rootConstitutions];
        function recurseFolders(folders: ConstitutionFolder[]) {
            for (const folder of folders) {
                constitutions.push(...folder.constitutions);
                if (folder.subFolders && folder.subFolders.length > 0) {
                    recurseFolders(folder.subFolders);
                }
            }
        }
        recurseFolders(hierarchy.rootFolders);
        return constitutions;
    }

    async function loadTemplateContent(templateId: string) {
        const selectedTemplate = allConstitutionsForTemplate.find(t => t.id === templateId);
        if (!selectedTemplate) return;

        constitutionTitle = selectedTemplate.title; // Pre-fill title
        templateLoading = true;
        constitutionText = 'Loading template content...';

        try {
            if (selectedTemplate.type === 'local') {
                constitutionText = selectedTemplate.text;
            } else { // type === 'remote'
                // Fetch content for remote constitutions using relativePath (stored in id)
                constitutionText = await fetchConstitutionContent(selectedTemplate.id);
            }
        } catch (error) {
            console.error("Failed to load template content:", error);
            constitutionText = `Error loading template: ${error instanceof Error ? error.message : String(error)}`;
        } finally {
            templateLoading = false;
            // Ensure textarea updates visually if needed
            await tick();
        }
    }


    async function handleSubmit() {
        if (!constitutionTitle.trim() || !constitutionText.trim()) return;

        isSubmitting = true;
        submitStatus = null;
        let localAddSuccess = false;
        let submitApiSuccess = false;
        let submitApiMessage = '';

        try {
            constitutionStore.addItem(constitutionTitle, constitutionText); // Use updated store name
            localAddSuccess = true;

            if (submitForReview) {
                const response = await submitConstitution({
                    text: constitutionText,
                    is_private: false // Submit for review implies potential public use
                });
                submitApiSuccess = response.status === 'success';
                submitApiMessage = response.message || (submitApiSuccess ? 'Submitted for review.' : 'Submission failed.');
            }

            if (localAddSuccess) {
                 submitStatus = {
                    success: true,
                    message: `Constitution '${constitutionTitle}' saved locally.` + (submitForReview ? ` ${submitApiMessage}` : '')
                };
                constitutionTitle = '';
                constitutionText = '';
                selectedTemplateId = null;

                onConstitutionAdded({ success: true });

                setTimeout(() => {
                    onClose();
                }, 2500); // Slightly longer delay
            } else {
                 // This case should ideally not happen if addLocalConstitution doesn't throw
                 submitStatus = { success: false, message: 'Failed to save constitution locally.' };
            }

        } catch (error) {
            console.error('Error during constitution save/submit:', error);
            submitStatus = {
                success: false,
                message: `An error occurred: ${error instanceof Error ? error.message : String(error)}`
            };
        } finally {
            isSubmitting = false;
        }
    }
    let allConstitutionsForTemplate = $derived((() => {
        const remoteConstitutions = flattenHierarchy(constitutionStore.globalHierarchy); // Use updated store name
        const remoteOptions: TemplateOption[] = remoteConstitutions
            // .filter(c => c.relativePath !== 'none') // Filtering 'none' might not be needed depending on backend
            .map((c): TemplateOption => ({ type: 'remote', id: c.relativePath, title: c.title }));

        const localOptions: TemplateOption[] = constitutionStore.localConstitutions.map((c: LocalConstitutionMetadata): TemplateOption => ({ type: 'local', id: c.localStorageKey, title: c.title, text: c.text })); // Use updated store name and add type

        return [...remoteOptions, ...localOptions].sort((a, b) => a.title.localeCompare(b.title));
    })()); // Immediately invoke the function expression
    // --- Reactive Logic & Effects ---
    // Fetch constitutions on component mount using the store's load method
    // No need to call load() explicitly, the store handles it internally via $effect.pre
    // globalConstitutionsStore.load();

    // Reactive statement to load template when selectedTemplateId changes
    $effect(() => {
        if (selectedTemplateId) {
            loadTemplateContent(selectedTemplateId);
        }
    });
</script>

<div class="add-constitution">
    <h2>Add New Constitution</h2>
    <div class="form-group">
        <!-- === Template Selection === -->
        <div class="form-row">
             <label for="template-select">Use as Template (Optional):</label>
             <select id="template-select" bind:value={selectedTemplateId} disabled={isSubmitting || templateLoading}>
                 <option value={null}>-- Select Template --</option>
                 {#each allConstitutionsForTemplate as template (template.id)}
                     <option value={template.id}>
                         {#if template.type === 'local'}[Local] {/if}{template.title}
                     </option>
                 {/each}
             </select>
        </div>

         <!-- === Constitution Title === -->
         <div class="form-row">
            <label for="constitution-title">Title:</label>
            <input
                type="text"
                id="constitution-title"
                bind:value={constitutionTitle}
                placeholder="Enter a title for your constitution"
                required
                disabled={isSubmitting || templateLoading}
            />
        </div>

        <!-- === Constitution Text === -->
        <textarea
            bind:value={constitutionText}
            placeholder="Enter your constitution text here..."
            rows="10"
            required
            disabled={isSubmitting || templateLoading}
        ></textarea>

        <!-- === Submit for Review Option === -->
        <div class="review-toggle">
             <label>
                 <input
                     type="checkbox"
                     bind:checked={submitForReview}
                     disabled={isSubmitting}
                 />
                 Submit for global review (optional)
             </label>
        </div>

        {#if submitForReview}
            <p class="review-note">
                If approved, this constitution may become publicly available.
            </p>
        {/if}

        <!-- === Status Message === -->
        {#if submitStatus}
            <p class="status-message {submitStatus.success ? 'success' : 'error'}">
                {submitStatus.message}
            </p>
        {/if}

        <!-- === Submit Button === -->
        <button
            class="submit-button"
            onclick={handleSubmit}
            disabled={!constitutionTitle.trim() || !constitutionText.trim() || isSubmitting || templateLoading}
        >
            {#if isSubmitting}
                Saving...
            {:else}
                Save Constitution
            {/if}
        </button>
    </div>
</div>

<style lang="scss">
    @use '../styles/mixins' as *;

    .add-constitution {
        padding: 0;
        width: 100%;
        margin: 0;
        height: 100%;
        overflow-y: auto;
        @include custom-scrollbar($track-bg: var(--bg-elevated));
    }

    h2 {
        color: var(--text-primary);
        margin-bottom: 20px;
        font-size: 1.2em;
    }

    .form-group {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    .form-row {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    label {
        font-size: 0.9em;
        color: var(--text-secondary);
    }

    input[type="text"],
    select,
    textarea {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--input-border);
        border-radius: var(--radius-sm);
        background: var(--bg-surface); // Use surface for inputs
        color: var(--text-primary);
        font-family: inherit;
        font-size: 0.95em;
    }
     input[type="text"]:focus,
     select:focus,
     textarea:focus {
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 2px var(--primary-lightest);
    }

    textarea {
        resize: vertical;
        min-height: 150px; // Adjust height
    }

    select {
        cursor: pointer;
    }

    .review-toggle {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;

        label {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            font-size: 0.9em;
            color: var(--text-primary);
        }
        input[type="checkbox"] {
             cursor: pointer;
             accent-color: var(--primary);
        }
    }


    .submit-button {
        align-self: flex-start;
        padding: 10px 20px;
        background-color: var(--primary);
        color: white;
        border: none;
        border-radius: var(--radius-sm);
        cursor: pointer;
        font-size: 0.95em;
        transition: background-color 0.2s, opacity 0.2s;
        margin-top: 8px;
    }

    .submit-button:hover:not(:disabled) {
        background-color: var(--primary-light);
    }

    .submit-button:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .review-note {
        font-size: 0.85em;
        color: var(--text-secondary);
        margin-top: -8px; // Reduce gap after checkbox
    }

    .status-message {
        padding: 10px 12px;
        border-radius: var(--radius-sm);
        font-size: 0.9em;
        margin-top: 8px;
    }

    .status-message.success {
        background-color: var(--success-bg, #e6f4ea);
        color: var(--success-text, #1e4620);
        border: 1px solid var(--success-border, #a7d7ae);
    }

    .status-message.error {
        background-color: var(--error-bg, #fce8e6);
        color: var(--error-text, #c5221f);
        border: 1px solid var(--error-border, #f4a9a8);
    }
</style>

<script lang="ts">
    import { submitConstitution } from '../api';
    import { createEventDispatcher } from 'svelte';
    
    const dispatch = createEventDispatcher();
    
    let constitutionText = '';
    let isPrivate = true;  // Default to private
    let isSubmitting = false;
    let submitStatus: { success?: boolean; message?: string } | null = null;

    async function handleSubmit() {
        if (!constitutionText.trim()) return;
        
        isSubmitting = true;
        submitStatus = null;
        
        try {
            const response = await submitConstitution({ 
                text: constitutionText, 
                is_private: isPrivate 
            });
            
            if (response.status === 'success') {
                submitStatus = { 
                    success: true, 
                    message: 'Constitution submitted successfully for review' 
                };
                constitutionText = '';  // Clear the form
                
                // Dispatch event to notify parent components
                dispatch('constitutionAdded', { success: true });
                
                // Auto-close modal after a delay
                setTimeout(() => {
                    dispatch('close');
                }, 2000);
            } else {
                submitStatus = { 
                    success: false, 
                    message: 'Failed to submit constitution' 
                };
            }
        } catch (error) {
            console.error('Failed to submit constitution:', error);
            submitStatus = { 
                success: false, 
                message: 'An error occurred while submitting the constitution' 
            };
        } finally {
            isSubmitting = false;
        }
    }
</script>

<div class="add-constitution">
    <h2>Add New Constitution</h2>
    <div class="form-group">
        <textarea
            bind:value={constitutionText}
            placeholder="Enter your constitution here..."
            rows="10"
            disabled={isSubmitting}
        ></textarea>
        <div class="privacy-toggle">
            <label class="toggle">
                <input
                    type="checkbox"
                    bind:checked={isPrivate}
                    disabled={isSubmitting}
                />
                <span class="slider"></span>
            </label>
            <span class="toggle-label">
                {isPrivate ? 'Private Constitution' : 'Public Constitution'}
            </span>
        </div>
        <p class="review-note">
            All submitted constitutions will be reviewed before being added to the system.
        </p>
        {#if submitStatus}
            <p class="status-message {submitStatus.success ? 'success' : 'error'}">
                {submitStatus.message}
            </p>
        {/if}
        <button 
            class="submit-button" 
            on:click={handleSubmit}
            disabled={!constitutionText.trim() || isSubmitting}
        >
            {isSubmitting ? 'Submitting...' : 'Submit Constitution For Review'}
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
        @include custom-scrollbar($track-bg: var(--bg-elevated)); // Use mixin, match modal content bg
    }

    h2 {
        color: var(--text-primary);
        margin-bottom: 20px;
    }

    .form-group {
        display: flex;
        flex-direction: column;
        gap: 16px;
    }

    textarea {
        width: 100%;
        padding: 12px;
        border: 1px solid var(--input-border);
        border-radius: 4px;
        background: var(--bg-elevated);
        color: var(--text-primary);
        font-family: inherit;
        resize: vertical;
        min-height: 200px;
    }

    textarea:focus {
        outline: none;
        border-color: var(--primary);
    }

    .submit-button {
        align-self: flex-start;
        padding: 10px 20px;
        background-color: var(--primary);
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 14px;
        transition: background-color 0.2s, opacity 0.2s;
    }

    .submit-button:hover:not(:disabled) {
        background-color: var(--primary-light);
    }

    .submit-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }

    .privacy-toggle {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .toggle {
        position: relative;
        display: inline-block;
        width: 48px;
        height: 24px;
    }

    .toggle input {
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
        background-color: var(--bg-elevated);
        border: 1px solid var(--input-border);
        transition: .4s;
        border-radius: 24px;
    }

    .slider:before {
        position: absolute;
        content: "";
        height: 18px;
        width: 18px;
        left: 2px;
        bottom: 2px;
        background-color: var(--text-secondary);
        transition: .4s;
        border-radius: 50%;
    }

    input:checked + .slider {
        background-color: var(--primary);
        border-color: var(--primary);
    }

    input:checked + .slider:before {
        transform: translateX(24px);
        background-color: white;
    }

    .toggle-label {
        color: var(--text-primary);
        font-size: 14px;
    }

    .status-message {
        padding: 12px;
        border-radius: 4px;
        font-size: 14px;
    }

    .status-message.success {
        background-color: var(--success-bg, #e6f4ea);
        color: var(--success-text, #1e4620);
    }

    .status-message.error {
        background-color: var(--error-bg, #fce8e6);
        color: var(--error-text, #c5221f);
    }
</style>

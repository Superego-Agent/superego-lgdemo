<script lang="ts">
        import { createEventDispatcher } from 'svelte';
        import { fade } from 'svelte/transition';
        import IconClose from '~icons/fluent/dismiss-24-regular';

        export let title: string = 'Constitution Info';
        export let description: string | undefined = undefined;
        export let content: string | undefined = undefined;
        export let isLoading: boolean = false;
        export let error: string | null = null;

        const dispatch = createEventDispatcher();

        function closeModal() {
            dispatch('close');
        }

        // Close modal on escape key press
        function handleKeydown(event: KeyboardEvent) {
            if (event.key === 'Escape') {
                closeModal();
            }
        }
    </script>

    <svelte:window on:keydown={handleKeydown}/>

    <div class="modal-overlay" on:click={closeModal} transition:fade={{ duration: 150 }}>
        <div class="modal-content" on:click|stopPropagation transition:fade={{ duration: 150, delay: 50 }}>
            <button class="close-button" on:click={closeModal} aria-label="Close modal">
                <IconClose />
            </button>
            <h2>{title}</h2>
            {#if description}
                <p class="description"><em>{description}</em></p>
            {/if}

            <hr />

            {#if isLoading}
                <div class="loading-indicator">Loading content...</div>
            {:else if error}
                <div class="error-message">Error loading content: {error}</div>
            {:else if content}
                <pre class="content-area">{content}</pre>
            {:else}
                <p>No content available.</p>
            {/if}
        </div>
    </div>

    <style>
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1000; /* Ensure it's on top */
        }

        .modal-content {
            background-color: var(--bg-surface);
            padding: var(--space-lg);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-xl);
            width: 90%;
            max-width: 700px; /* Limit max width */
            max-height: 80vh; /* Limit max height */
            overflow-y: auto; /* Allow scrolling for content */
            position: relative; /* For close button positioning */
            scrollbar-width: thin;
            scrollbar-color: var(--primary-light) var(--bg-surface);
        }
         .modal-content::-webkit-scrollbar { width: 6px; }
         .modal-content::-webkit-scrollbar-track { background: var(--bg-surface); }
         .modal-content::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }


        .close-button {
            position: absolute;
            top: var(--space-sm);
            right: var(--space-sm);
            background: none;
            border: none;
            font-size: 1.5em; /* Make icon larger */
            cursor: pointer;
            color: var(--text-secondary);
            padding: var(--space-xs);
             line-height: 1;
        }
        .close-button:hover {
            color: var(--text-primary);
        }

        h2 {
            margin-top: 0;
            margin-bottom: var(--space-sm);
            color: var(--text-primary);
        }

        .description {
            font-size: 0.9em;
            color: var(--text-secondary);
            margin-bottom: var(--space-md);
        }

        hr {
            border: none;
            border-top: 1px solid var(--input-border);
            margin: var(--space-md) 0;
        }

        .content-area {
            white-space: pre-wrap; /* Wrap long lines */
            word-wrap: break-word; /* Break long words */
            font-family: var(--font-mono);
            font-size: 0.85em;
            background-color: var(--bg-primary); /* Slightly different background */
            padding: var(--space-md);
            border-radius: var(--radius-md);
            border: 1px solid var(--input-border);
            max-height: 50vh; /* Limit height within modal */
            overflow-y: auto; /* Scroll specifically for content */
            scrollbar-width: thin;
            scrollbar-color: var(--primary-light) var(--bg-primary);
        }
         .content-area::-webkit-scrollbar { width: 6px; }
         .content-area::-webkit-scrollbar-track { background: var(--bg-primary); }
         .content-area::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }


        .loading-indicator, .error-message {
            padding: var(--space-lg);
            text-align: center;
            color: var(--text-secondary);
            font-style: italic;
        }
        .error-message {
            color: var(--error);
        }
    </style>

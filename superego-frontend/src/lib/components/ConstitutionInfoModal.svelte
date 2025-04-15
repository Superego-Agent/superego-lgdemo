<script lang="ts">
    import { fade } from 'svelte/transition';
    import IconClose from '~icons/fluent/dismiss-24-regular';
    import { marked } from 'marked';
    import DOMPurify from 'dompurify';

    interface Props {
        title?: string;
        description?: string | undefined;
        content?: string | undefined;
        isLoading?: boolean;
        error?: string | null;
        onClose?: () => void;
    }

    let {
        title = 'Constitution Info',
        description = undefined,
        content = undefined,
        isLoading = false,
        error = null,
        onClose = () => {}
    }: Props = $props();

    // Parse and sanitize markdown content
    let parsedHtml = $derived(content ? DOMPurify.sanitize(marked.parse(content, { async: false })) : '');

        function closeModal() {
            onClose();
        }

        // Close modal on escape key press
        function handleKeydown(event: KeyboardEvent) {
            if (event.key === 'Escape') {
                closeModal();
            }
        }
    </script>

    <svelte:window onkeydown={handleKeydown}/>

    <div
      class="modal-overlay"
      onclick={(e) => { if (e.target === e.currentTarget) closeModal(); }}
      transition:fade={{ duration: 150 }}
      role="button"
      aria-label="Close modal"
      tabindex="0"
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') closeModal(); }}
    >
        <div class="modal-content" transition:fade={{ duration: 150, delay: 50 }}>
            <button class="close-button" onclick={closeModal} aria-label="Close modal">
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
                <div class="content-area">{@html parsedHtml}</div>
            {:else}
                <p>No content available.</p>
            {/if}
        </div>
    </div>

    <style lang="scss">
        @use '../styles/mixins' as *;

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
            @include base-card($shadow: var(--shadow-xl)); // Use mixin, override shadow
            padding: var(--space-lg); // Keep specific padding
            width: 90%;
            max-width: 700px;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
            @include custom-scrollbar($track-bg: var(--bg-surface), $thumb-bg: var(--primary-light), $width: 6px); // Use mixin
        }

        .close-button {
            @include icon-button($padding: var(--space-xs)); // Use mixin
            position: absolute;
            top: var(--space-sm);
            right: var(--space-sm);
            font-size: 1.5em; // Keep specific size

            &:hover { // Override mixin hover
                color: var(--text-primary);
                background-color: transparent; // Ensure no background on hover
            }
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
            /* Removed pre-wrap, word-wrap, font-family */
            font-size: 0.9em; /* Slightly larger default font for rendered HTML */
            background-color: var(--bg-primary); /* Slightly different background */
            padding: var(--space-md);
            border-radius: var(--radius-md);
            border: 1px solid var(--input-border);
            max-height: 50vh; /* Limit height within modal */
            overflow-y: auto;

        /* Style headings within the rendered markdown */
        .content-area h1 {
            font-size: 1.4em; /* Or adjust as needed */
            line-height: 1.2;
            margin-top: 0.8em;
            margin-bottom: 0.4em;
        }
        .content-area h2 {
            font-size: 1.2em; /* Or adjust as needed */
            line-height: 1.2;
            margin-top: 0.6em;
            margin-bottom: 0.3em;
        }
        /* Add rules for h3, h4, etc. if needed */


            @include custom-scrollbar($track-bg: var(--bg-primary), $thumb-bg: var(--primary-light), $width: 6px); // Use mixin
        }

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

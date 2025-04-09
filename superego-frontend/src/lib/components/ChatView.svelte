<script lang="ts">
    import { historyCacheStore, activeStreamsStore } from '../stores'; // Import activeStreamsStore
    import { getLatestHistory } from '../api';
    import { fade } from 'svelte/transition';
    import MessageCard from './MessageCard.svelte';
    import ErrorIcon from '~icons/fluent/warning-24-regular';
    // Types (HistoryEntry, MessageType) are globally available

    export let threadId: string;

    let isLoading = false; // Local loading state ONLY for initial fetch
    let componentError: string | null = null; // Local error state for fetch failure

    // Reactive derivations from the central cache
    $: historyEntry = threadId ? $historyCacheStore[threadId] : null;
    $: displayedMessages = historyEntry?.values?.messages ?? [];
    // Reactive derivation for streaming status
    $: isStreaming = threadId ? $activeStreamsStore[threadId] ?? false : false;

    // Fetch initial history ONLY if threadId is valid and not already in cache
    $: if (threadId && !$historyCacheStore[threadId] && !isLoading) {
        loadInitialHistory(threadId);
    }

    async function loadInitialHistory(id: string) {
        isLoading = true;
        componentError = null;
        try {
            await getLatestHistory(id);
        } catch (error: unknown) {
            console.error(`[ChatView] Error loading initial history for thread ${id}:`, error);
            const message = error instanceof Error ? error.message : String(error);
            if ( ($historyCacheStore[id]?.values?.messages ?? []).length === 0 ) {
                 componentError = `Failed to load conversation history: ${message}`;
            } else {
                 console.warn(`[ChatView] Error occurred during fetch for thread ${id}, but messages already exist. Not showing component-level error.`);
            }
        } finally {
            isLoading = false;
        }
    }

    // Clear local error when threadId changes
    $: if (threadId) {
        componentError = null;
        if (isLoading) isLoading = false;
    }

</script>

<div class="chat-view-content">
    {#if isLoading && displayedMessages.length === 0}
        <!-- Show loading indicator only during initial fetch when no messages are yet available -->
        <div class="status-indicator loading" transition:fade={{ duration: 200 }}>
            <div class="spinner"></div>
        </div>
    {:else if componentError && displayedMessages.length === 0}
        <!-- Show error indicator only if initial fetch failed AND no messages are available -->
        <div class="status-indicator error" transition:fade={{ duration: 200 }}>
            <div class="icon"><ErrorIcon /></div>
            <p>{componentError}</p>
        </div>
    {/if}

    <!-- Render messages whenever they exist in the cache -->
    {#if displayedMessages.length > 0}
        {#each displayedMessages as message (message.id)}
            <div transition:fade={{ duration: 300 }}>
                <MessageCard {message} />
            </div>
        {/each}
    {/if}

    <!-- Streaming Indicator -->
    {#if isStreaming}
        <div class="status-indicator streaming" transition:fade={{ duration: 150, delay: 150 }}>
             <div class="spinner small"></div>
             <span>Agent thinking...</span>
        </div>
    {/if}
</div>

<style lang="scss">
    @use '../styles/mixins' as *;

    .chat-view-content {
        display: flex;
        flex-direction: column;
        gap: var(--space-md);
        height: 100%;
        width: 100%;
        position: relative;
        padding-bottom: 2.5rem; /* Add padding to prevent overlap with streaming indicator */
    }

    .status-indicator {
        text-align: center;
        margin: auto; /* Center initial load/error */
        padding: var(--space-xl) 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-sm);

        &.loading {
             padding: var(--space-md);
        }

        &.error {
            color: var(--error);
            font-style: normal;
            p { margin: 0; font-size: 0.9em; }
            .icon {
                font-size: 1.8em;
                opacity: 0.8;
                margin-bottom: var(--space-xs);
            }
        }

        &.streaming {
            position: absolute; /* Position at the bottom */
            bottom: var(--space-xs);
            left: 50%;
            transform: translateX(-50%);
            flex-direction: row; /* Keep spinner and text inline */
            padding: var(--space-xs) var(--space-sm);
            margin: 0; /* Override auto margin */
            font-size: 0.8em;
            color: var(--text-secondary);
            background-color: var(--bg-secondary-alpha); /* Slightly transparent background */
            border-radius: var(--radius-sm);
            z-index: 5;
            backdrop-filter: blur(2px);
        }

        .spinner {
             @include loading-spinner(1.5em, 2px, var(--text-secondary));
             &.small {
                 @include loading-spinner(1em, 2px, var(--text-secondary));
             }
        }
    }
</style>
<script lang="ts">
	import { threadCacheStore } from '$lib/stores';
	import { tick } from 'svelte'; // Add tick import
	import { derived } from 'svelte/store';
	import MessageCard from './MessageCard.svelte'; // Use existing component

	export let threadId: string;

	// Derive the specific cache entry for this threadId
	const cacheEntry = derived(threadCacheStore, ($cache) => $cache[threadId]);

	let messageListContainer: HTMLDivElement; // Define container variable

	// Derive individual state pieces for easier use in the template
	let history: HistoryEntry | null = null;
	let isStreaming: boolean = false;
	let error: string | null = null;
    let showSpinner: boolean = false;

	$: {
		const entry = $cacheEntry;
		history = entry?.history ?? null;
		isStreaming = entry?.isStreaming ?? false;
		error = entry?.error ?? null;
        // Show spinner only if actively streaming
        showSpinner = isStreaming;
	}

    // Reactive statement to derive messages array
    let messages: MessageType[] = [];
    $: messages = history?.values?.messages ?? [];

    // // Reactive statement for conditional auto-scrolling
    // $: if (messageListContainer && messages) {
    //     const scrollToBottomIfNear = async () => {
    //         const { scrollHeight, scrollTop, clientHeight } = messageListContainer;
    //         // Threshold in pixels - adjust as needed
    //         const scrollThreshold = 50;
    //         // Check if user is near the bottom *before* the DOM updates
    //         const isNearBottom = scrollHeight - scrollTop - clientHeight < scrollThreshold;

    //         // Wait for DOM update after messages change
    //         await tick();

    //         // Only scroll if the user was already near the bottom
    //         if (isNearBottom) {
    //             messageListContainer.scrollTop = messageListContainer.scrollHeight;
    //         }
    //     };
    //     scrollToBottomIfNear();
    // }

</script>

<div class="chat-view">
	{#if error}
		<div class="error-message">Error loading/streaming thread: {error}</div>
	{/if}

	{#if history}
		<div class="message-list" bind:this={messageListContainer}>
			{#each messages as message, i (message.nodeId + '-' + i)} <!-- Basic key, might need improvement -->
				<MessageCard {message} />
			{/each}
            <!-- No explicit empty state message -->
		</div>
	{/if}

	{#if showSpinner}
		<div class="spinner-container">
            <div class="spinner"></div>
        </div>
	{/if}

</div>

<style lang="scss">
	.chat-view {
		flex-grow: 1;
		display: flex;
		flex-direction: column;
        overflow: hidden; // Prevent content overflow issues
        position: relative; // Needed for absolute positioning of spinner
	}

	.message-list {
		flex-grow: 1;
		overflow-y: auto; // Allow scrolling through messages
		padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.75rem; // Space between messages
	}

	.error-message {
		padding: 1rem;
		background-color: var(--color-error-bg, #f8d7da);
		color: var(--color-error-text, #721c24);
		border: 1px solid var(--color-error-border, #f5c6cb);
		border-radius: 4px;
		margin: 1rem;
	}

    .spinner-container {
        position: absolute;
        bottom: 1rem;
        right: 1rem;
        width: 24px; /* Adjust size as needed */
        height: 24px;
        pointer-events: none; /* Prevent interaction */
    }

    .spinner {
        border: 3px solid rgba(0, 0, 0, 0.1);
        border-left-color: var(--color-primary, #007bff); /* Use theme color if available */
        border-radius: 50%;
        width: 100%;
        height: 100%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }

</style>
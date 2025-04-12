<!-- @migration-task Error while migrating Svelte code: can't migrate `$: messages = history?.values?.messages ?? [];` to `$derived` because there's a variable named derived.
     Rename the variable and try again or migrate by hand. -->
<script lang="ts">
	import { threadStore } from '$lib/state/threads.svelte'; // Import the new thread store
	import { tick } from 'svelte';
	import MessageCard from './MessageCard.svelte';

	let { threadId } = $props<{ threadId: string }>(); // Use $props for runes mode
	// Derive directly from the $state variable
	const cacheEntry = $derived(threadStore.threadCacheStore[threadId]); // Use threadStore

	let messageListContainer: any = $state(); 

	let historyState: HistoryEntry | null = $state(null);
	let isStreaming: boolean = $state(false);
	let error: string | null = $state(null);
    let showSpinner: boolean = $state(false);

	// Effect to update local state based on derived cacheEntry
	$effect.pre(() => {
		const entry = cacheEntry; // Use derived value
		historyState = entry?.history ?? null;
		isStreaming = entry?.isStreaming ?? false;
		error = entry?.error ?? null;
		showSpinner = isStreaming;
	});


</script>
<div class="chat-view">
	{#if error}
		<div class="error-message">Error loading/streaming thread: {error}</div>
	{/if}

	{#if history}
		<div class="message-list" bind:this={messageListContainer}>
			{#each historyState?.values?.messages ?? [] as message, i (message.nodeId + '-' + i)}
				<MessageCard {message} />
			{/each}
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
		overflow-y: auto;
		padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
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
        width: 24px;
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
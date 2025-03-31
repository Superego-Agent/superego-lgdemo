<script lang="ts">
	import { messages, isLoading, globalError } from '../stores';
	import MessageCard from './MessageCard.svelte';
	import ChatInput from './ChatInput.svelte';
	import { afterUpdate } from 'svelte';

	let chatContainer: HTMLElement;

	// Scroll to bottom when messages update
	afterUpdate(() => {
		if (chatContainer) {
			chatContainer.scrollTop = chatContainer.scrollHeight;
		}
	});
</script>

<div class="chat-interface">
	{#if $globalError}
		<div class="error-banner">Error: {$globalError}</div>
	{/if}

	<div class="messages-container" bind:this={chatContainer}>
		{#each $messages as message (message.id)}
			<MessageCard {message} />
		{:else}
			<p class="empty-chat">Send a message to start the conversation.</p>
		{/each}

		{#if $isLoading}
			<div class="loading-indicator">
				<div class="spinner"></div>
				<span>Thinking...</span>
			</div>
		{/if}
	</div>

	<ChatInput />
</div>

<style>
	.chat-interface {
		flex-grow: 1;
		display: flex;
		flex-direction: column;
		height: 100%; /* Needed for flex layout */
        overflow: hidden; /* Prevent content spill */
        background-color: #f9f9f9;
	}

	.error-banner {
		background-color: #f8d7da;
		color: #721c24;
		padding: 10px 15px;
		border-bottom: 1px solid #f5c6cb;
		text-align: center;
		font-size: 0.9em;
	}

	.messages-container {
		flex-grow: 1;
		overflow-y: auto;
		padding: 20px;
        display: flex;
        flex-direction: column;
        gap: 15px;
	}

    .empty-chat {
        text-align: center;
        color: #888;
        margin-top: 40px;
        font-style: italic;
    }

	.loading-indicator {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 15px;
		color: #555;
        gap: 8px;
        font-style: italic;
	}

	.spinner {
		border: 3px solid #f3f3f3; /* Light grey */
		border-top: 3px solid #555; /* Dark grey */
		border-radius: 50%;
		width: 16px;
		height: 16px;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}
</style>
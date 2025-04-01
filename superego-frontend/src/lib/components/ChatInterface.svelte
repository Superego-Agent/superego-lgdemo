<script lang="ts">
	import { messages, isLoading, globalError } from '../stores';
	import MessageCard from './MessageCard.svelte';
	import ChatInput from './ChatInput.svelte';
	import { afterUpdate } from 'svelte';
	import { slide, fade } from 'svelte/transition';

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
		<div class="error-banner" in:slide={{ duration: 300 }} out:slide={{ duration: 300 }}>
			<div class="error-content">
				<span class="error-icon">⚠️</span>
				<span>Error: {$globalError}</span>
			</div>
		</div>
	{/if}

	<div class="messages-container" bind:this={chatContainer}>
		{#each $messages as message (message.id)}
			<MessageCard {message} />
		{:else}
			<div class="empty-chat" in:fade={{ duration: 500 }}>
				<div class="empty-chat-icon">💬</div>
				<p>Send a message to start the conversation</p>
			</div>
		{/each}

		{#if $isLoading}
			<div class="loading-indicator" in:fade={{ duration: 200 }}>
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
        background-color: var(--bg-primary);
        width: 100%; /* Ensure it takes full width */
        position: relative; /* For absolute positioning if needed */
	}
	
	/* Mobile styles */
    @media (max-width: 768px) {
        .chat-interface {
            /* When sidebar is on top in mobile view, take remaining height */
            flex: 1;
            min-height: 0; /* Allow shrinking */
        }
    }

	.error-banner {
		background-color: var(--error-bg);
		color: var(--error);
		padding: var(--space-md);
		border-bottom: 1px solid var(--error);
		text-align: center;
		font-size: 0.9em;
		box-shadow: var(--shadow-md);
	}
	
	.error-content {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-sm);
	}
	
	.error-icon {
		font-size: 1.2em;
	}

	.messages-container {
		flex-grow: 1;
		overflow-y: auto;
		padding: var(--space-lg);
        display: flex;
        flex-direction: column;
        gap: var(--space-md);
        -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
		scrollbar-width: thin;
		scrollbar-color: var(--primary-light) var(--bg-surface);
	}
	
	.messages-container::-webkit-scrollbar {
		width: 8px;
	}
	
	.messages-container::-webkit-scrollbar-track {
		background: var(--bg-surface);
		border-radius: var(--radius-pill);
	}
	
	.messages-container::-webkit-scrollbar-thumb {
		background-color: var(--primary-light);
		border-radius: var(--radius-pill);
	}
	
	/* Mobile styles */
    @media (max-width: 768px) {
        .messages-container {
            padding: var(--space-md) var(--space-sm);
        }
    }

    .empty-chat {
        text-align: center;
        color: var(--text-secondary);
        margin: auto;
        font-style: italic;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-md);
    }
	
	.empty-chat-icon {
		font-size: 2.5em;
		margin-bottom: var(--space-sm);
		opacity: 0.7;
	}

	.loading-indicator {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: var(--space-md);
		color: var(--text-secondary);
        gap: var(--space-sm);
        font-style: italic;
	}

	.spinner {
		border: 3px solid rgba(255, 255, 255, 0.1);
		border-top: 3px solid var(--secondary);
		border-radius: 50%;
		width: 20px;
		height: 20px;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}
</style>

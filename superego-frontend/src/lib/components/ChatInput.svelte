<script lang="ts">
	import { messages, currentThreadId, currentMode, activeConstitutionIds, compareSets, isLoading } from '../stores';
	import { streamRun, streamCompareRun } from '../api'; // Use mock API
	import { fly, scale } from 'svelte/transition';

	let userInput: string = '';
	let inputElement: HTMLTextAreaElement;
	let isExpanded = false;

	async function handleSubmit() {
		const trimmedInput = userInput.trim();
		if (!trimmedInput || $isLoading) return;

		const threadId = $currentThreadId;
		const mode = $currentMode;
		const humanMessage: HumanMessage = {
			id: `msg-${Date.now()}`,
			sender: 'human',
			content: trimmedInput,
			timestamp: Date.now()
		};

		// Add human message to store immediately
		messages.update(m => [...m, humanMessage]);
		userInput = ''; // Clear input field
		isExpanded = false; // Reset expanded state

		try {
			if (mode === 'compare') {
				const sets = $compareSets;
				if (sets.length === 0) {
					alert("Please configure at least one comparison set in the sidebar.");
					// Remove the human message we just added optimistically? Or show error?
					messages.update(m => m.slice(0, -1)); // Remove last message
					return;
				}
				await streamCompareRun(trimmedInput, sets);
			} else {
				// Handles 'chat' and 'use' modes
				const constitutions = (mode === 'use') ? $activeConstitutionIds : ['none'];
				await streamRun(trimmedInput, threadId, constitutions);
			}
		} catch (err) {
			console.error("Error triggering stream:", err);
			// Error should be handled within the API mock/actual implementation and reflected in stores
		}
	}

	function handleFocus() {
		isExpanded = true;
	}

	function handleBlur() {
		if (!userInput.trim()) {
			isExpanded = false;
		}
	}
</script>

<form class="chat-input-form" class:expanded={isExpanded} on:submit|preventDefault={handleSubmit}>
	<div class="textarea-container">
		<textarea
			bind:this={inputElement}
			bind:value={userInput}
			placeholder="Send a message (e.g., 'Hello', or 'Explain X using tool')..."
			rows={isExpanded ? 3 : 1}
			disabled={$isLoading}
			on:focus={handleFocus}
			on:blur={handleBlur}
			on:keydown={(e) => { 
				if (e.key === 'Enter' && !e.shiftKey) { 
					e.preventDefault(); 
					handleSubmit(); 
				} 
			}}
		/>
	</div>
	
	<button 
		type="submit" 
		disabled={!userInput.trim() || $isLoading}
		class:loading={$isLoading}
		in:scale|local={{ duration: 150, start: 0.8 }}
	>
		{#if $isLoading}
			<div class="button-spinner"></div>
		{:else}
			<span class="send-icon">↗</span>
		{/if}
	</button>
</form>

<style>
	.chat-input-form {
		display: flex;
		padding: var(--space-md);
		border-top: 1px solid var(--input-border);
        background-color: var(--bg-surface);
        gap: var(--space-md);
		transition: padding 0.2s ease;
	}
	
	.chat-input-form.expanded {
		padding: var(--space-lg) var(--space-md);
	}

	.textarea-container {
		flex-grow: 1;
		position: relative;
		box-shadow: var(--shadow-sm);
		border-radius: var(--radius-lg);
		transition: all 0.3s ease;
	}
	
	.expanded .textarea-container {
		box-shadow: var(--shadow-md);
	}

	textarea {
		width: 100%;
		padding: var(--space-md) var(--space-lg);
		border: 1px solid var(--input-border);
		background-color: var(--input-bg);
		color: var(--text-primary);
		border-radius: var(--radius-lg);
		resize: none; /* Prevent manual resize */
        font-family: inherit;
        font-size: 1em;
        line-height: 1.4;
        max-height: 150px; /* Limit growth */
        transition: all 0.2s ease;
	}
	
    textarea:focus {
        border-color: var(--input-focus);
        outline: none;
		box-shadow: 0 0 0 2px rgba(157, 70, 255, 0.2);
    }
	
    textarea:disabled {
        background-color: var(--bg-surface);
        cursor: not-allowed;
		opacity: 0.7;
    }

	button {
		height: 44px;
		width: 44px;
		border: none;
		background-color: var(--primary);
		color: white;
		border-radius: var(--radius-pill);
		cursor: pointer;
		font-size: 1.2em;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
		box-shadow: var(--shadow-sm);
	}

	button:hover:not(:disabled) {
		background-color: var(--primary-light);
		transform: translateY(-2px);
		box-shadow: var(--shadow-md);
	}
	
    button:disabled {
        background-color: var(--primary-dark);
        cursor: not-allowed;
		opacity: 0.6;
		transform: scale(0.95);
    }
	
	button.loading {
		background-color: var(--primary-dark);
	}

    .button-spinner {
		border: 3px solid rgba(255, 255, 255, 0.3);
		border-top: 3px solid #fff;
		border-radius: 50%;
		width: 18px;
		height: 18px;
		animation: spin 1s linear infinite;
	}
	
	.send-icon {
		font-weight: bold;
		transform: rotate(45deg);
		display: inline-block;
	}
	
    /* Reusing spinner animation */
	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}
	
	/* Mobile adjustments */
	@media (max-width: 768px) {
		.chat-input-form {
			padding: var(--space-sm);
			gap: var(--space-sm);
		}
		
		.chat-input-form.expanded {
			padding: var(--space-md) var(--space-sm);
		}
		
		textarea {
			padding: var(--space-sm) var(--space-md);
		}
		
		button {
			height: 40px;
			width: 40px;
		}
	}
</style>

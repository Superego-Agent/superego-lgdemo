<script lang="ts">
	import { messages, currentThreadId, currentMode, activeConstitutionIds, compareSets, isLoading } from '../stores';
	import { streamRun, streamCompareRun } from '../api'; // Use mock API

	let userInput: string = '';

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

        // Call the appropriate mock API function based on mode
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
</script>

<form class="chat-input-form" on:submit|preventDefault={handleSubmit}>
	<textarea
		bind:value={userInput}
		placeholder="Send a message (e.g., 'Hello', or 'Explain X using tool')..."
        rows="2"
		disabled={$isLoading}
        on:keydown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }}
	/>
	<button type="submit" disabled={!userInput.trim() || $isLoading}>
		{#if $isLoading}
            <div class="button-spinner"></div>
        {:else}
            Send
        {/if}
	</button>
</form>

<style>
	.chat-input-form {
		display: flex;
		padding: 15px;
		border-top: 1px solid #ddd;
        background-color: #fff;
        gap: 10px;
	}

	textarea {
		flex-grow: 1;
		padding: 10px 15px;
		border: 1px solid #ccc;
		border-radius: 6px;
		resize: none; /* Prevent manual resize */
        font-family: inherit;
        font-size: 1em;
        line-height: 1.4;
        max-height: 100px; /* Limit growth */
        transition: border-color 0.2s;
	}
    textarea:focus {
        border-color: #007bff;
        outline: none;
    }
    textarea:disabled {
        background-color: #f0f0f0;
        cursor: not-allowed;
    }

	button {
		padding: 0 20px;
		border: none;
		background-color: #007bff;
		color: white;
		border-radius: 6px;
		cursor: pointer;
		font-size: 1em;
        transition: background-color 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 80px; /* Ensure button doesn't shrink too much */
	}

	button:hover:not(:disabled) {
		background-color: #0056b3;
	}
    button:disabled {
        background-color: #a0cfff;
        cursor: not-allowed;
    }

    .button-spinner {
		border: 3px solid rgba(255, 255, 255, 0.3);
		border-top: 3px solid #fff;
		border-radius: 50%;
		width: 16px;
		height: 16px;
		animation: spin 1s linear infinite;
	}
    /* Reusing spinner animation from ChatInterface */
	@keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}
</style>
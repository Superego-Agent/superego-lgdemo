<script lang="ts">
	import { onMount } from 'svelte';
	import {
		currentMode,
		availableConstitutions,
		activeConstitutionIds,
		compareSets,
		availableThreads,
        currentThreadId,
        messages,
        isLoading,
	} from '../stores';
	import { fetchConstitutions, fetchThreads, createNewThread, fetchHistory } from '../api';
    import ConstitutionDropdown from './ConstitutionDropdown.svelte'; // Placeholder
    import CompareInterface from './CompareInterface.svelte'; // Placeholder

    onMount(async () => {
        // Fetch initial data for sidebar
        availableConstitutions.set(await fetchConstitutions());
        availableThreads.set(await fetchThreads());
    });

    async function handleNewChat() {
        if ($isLoading) return;
        console.log("Starting new chat...");
        try {
            const newThread = await createNewThread();
            currentThreadId.set(newThread.thread_id);
            messages.set([]); // Clear messages
            availableThreads.set(await fetchThreads()); // Refresh thread list
            currentMode.set('chat'); // Reset mode
        } catch (error) {
            console.error("Failed to create new chat:", error);
            // Show error to user?
        }
    }

    async function loadThread(threadId: string) {
        if ($isLoading || threadId === $currentThreadId) return;
        console.log(`Loading thread: ${threadId}`);
        try {
             currentThreadId.set(threadId);
             const history = await fetchHistory(threadId);
             messages.set(history.messages);
        } catch (error) {
             console.error(`Failed to load history for ${threadId}:`, error);
             // Show error? Reset state?
        }
    }

</script>

<div class="sidebar">
	<h2>Superego Demo</h2>

    <button class="new-chat-button" on:click={handleNewChat} disabled={$isLoading}>
        {#if $isLoading && !$currentThreadId} <div class="button-spinner"></div> {:else} + New Chat {/if}
    </button>

    <div class="threads-section">
        <h4>History</h4>
        <ul class="thread-list">
            {#each $availableThreads as thread (thread.thread_id)}
                <li class:active={thread.thread_id === $currentThreadId}>
                    <button on:click={() => loadThread(thread.thread_id)} disabled={$isLoading}>
                        {thread.title || thread.thread_id.substring(0, 8)}
                    </button>
                </li>
            {:else}
                <li>No history yet.</li>
            {/each}
        </ul>
    </div>


	<div class="mode-switcher">
        <h4>Mode</h4>
		<label>
			<input type="radio" bind:group={$currentMode} value="chat" /> Chat
		</label>
		<label>
			<input type="radio" bind:group={$currentMode} value="use" /> Use Constitution(s)
		</label>
		<label>
			<input type="radio" bind:group={$currentMode} value="compare" /> Compare Constitutions
		</label>
	</div>

	<div class="mode-options">
		{#if $currentMode === 'use'}
			<h4>Active Constitution(s)</h4>
            <ConstitutionDropdown />
		{:else if $currentMode === 'compare'}
			<h4>Comparison Sets</h4>
            <CompareInterface />
		{:else}
            <p class="mode-info">Standard chat mode.</p>
        {/if}
	</div>

</div>

<style>
	.sidebar {
		width: 300px;
		min-width: 250px; /* Prevent excessive shrinking */
		background-color: #f0f0f0;
		padding: 20px;
		display: flex;
		flex-direction: column;
		border-right: 1px solid #ddd;
        height: 100%;
        overflow-y: auto;
	}

    h2 {
        text-align: center;
        margin-bottom: 20px;
        color: #333;
    }

    .new-chat-button {
        width: 100%;
        padding: 10px 15px;
        margin-bottom: 25px;
        background-color: #28a745;
        color: white;
        border: none;
        border-radius: 5px;
        cursor: pointer;
        font-size: 1em;
        transition: background-color 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .new-chat-button:hover:not(:disabled) {
        background-color: #218838;
    }
     .new-chat-button:disabled {
        background-color: #8fdfa3;
        cursor: not-allowed;
    }

    .threads-section {
        margin-bottom: 25px;
    }

    .thread-list {
        list-style: none;
        padding: 0;
        margin: 0;
        max-height: 200px; /* Limit height */
        overflow-y: auto;
        border: 1px solid #ccc;
        border-radius: 4px;
        background-color: #fff;
    }
    .thread-list li {
        border-bottom: 1px solid #eee;
    }
     .thread-list li:last-child {
        border-bottom: none;
    }
    .thread-list li button {
        width: 100%;
        text-align: left;
        padding: 8px 12px;
        background: none;
        border: none;
        cursor: pointer;
        font-size: 0.9em;
        color: #333;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
     .thread-list li button:hover:not(:disabled) {
         background-color: #e9ecef;
     }
      .thread-list li button:disabled {
         color: #999;
         cursor: not-allowed;
     }
    .thread-list li.active button {
        background-color: #007bff;
        color: white;
        font-weight: bold;
    }


	.mode-switcher {
		margin-bottom: 20px;
        border-top: 1px solid #ccc;
        padding-top: 15px;
	}
    .mode-switcher label {
        display: block;
        margin-bottom: 8px;
        cursor: pointer;
    }
     .mode-switcher input {
         margin-right: 8px;
     }

    .mode-options {
        flex-grow: 1; /* Takes remaining space */
         border-top: 1px solid #ccc;
        padding-top: 15px;
    }
    .mode-options h4 { margin-bottom: 10px; }

    .mode-info {
        font-size: 0.9em;
        color: #666;
        font-style: italic;
    }

    h4 { margin-top: 0; margin-bottom: 10px; color: #555; }

    /* Reusing spinner animation */
    .button-spinner {
		border: 3px solid rgba(255, 255, 255, 0.3);
		border-top: 3px solid #fff;
		border-radius: 50%;
		width: 16px;
		height: 16px;
		animation: spin 1s linear infinite;
        margin-right: 8px; /* Space between spinner and text if needed */
	}
    @keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}

</style>
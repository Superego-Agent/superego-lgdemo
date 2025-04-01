<script lang="ts">
	import { onMount } from 'svelte';
	import { fade, slide, fly } from 'svelte/transition';
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
	<h2>
		<span class="logo-text" in:slide={{ delay: 100, duration: 500 }}>Superego</span>
		<span class="subtitle">Demo</span>
	</h2>

    <button class="new-chat-button" on:click={handleNewChat} disabled={$isLoading}>
        {#if $isLoading && !$currentThreadId} 
			<div class="button-spinner"></div>
		{:else} 
			<span class="btn-icon">+</span>
			<span>New Chat</span>
		{/if}
    </button>

    <div class="sidebar-section threads-section">
        <h4><span class="section-icon">📜</span> History</h4>
        <ul class="thread-list">
            {#each $availableThreads as thread, i (thread.thread_id)}
                <li 
                    class:active={thread.thread_id === $currentThreadId}
                    in:fly={{ y: 10, delay: i * 50, duration: 200 }}
                >
                    <button on:click={() => loadThread(thread.thread_id)} disabled={$isLoading}>
                        {thread.title || thread.thread_id.substring(0, 8)}
                    </button>
                </li>
            {:else}
                <li class="empty-list">No history yet.</li>
            {/each}
        </ul>
    </div>


	<div class="sidebar-section mode-switcher">
        <h4><span class="section-icon">🔄</span> Mode</h4>
		<label class="mode-option" class:selected={$currentMode === 'chat'}>
			<input type="radio" bind:group={$currentMode} value="chat" /> 
			<span>Chat</span>
		</label>
		<label class="mode-option" class:selected={$currentMode === 'use'}>
			<input type="radio" bind:group={$currentMode} value="use" /> 
			<span>Use Constitution(s)</span>
		</label>
		<label class="mode-option" class:selected={$currentMode === 'compare'}>
			<input type="radio" bind:group={$currentMode} value="compare" /> 
			<span>Compare Constitutions</span>
		</label>
	</div>

	<div class="sidebar-section mode-options">
		{#if $currentMode === 'use'}
			<h4><span class="section-icon">📋</span> Active Constitution(s)</h4>
            <ConstitutionDropdown />
		{:else if $currentMode === 'compare'}
			<h4><span class="section-icon">⚖️</span> Comparison Sets</h4>
            <CompareInterface />
		{:else}
            <p class="mode-info" in:fade={{ duration: 300 }}>Standard chat mode. AI will respond directly.</p>
        {/if}
	</div>

</div>

<style>
	.sidebar {
		width: 320px;
		min-width: 270px; /* Prevent excessive shrinking */
		background-color: var(--bg-sidebar);
		padding: var(--space-lg);
		display: flex;
		flex-direction: column;
		border-right: 1px solid var(--input-border);
        height: 100%;
        overflow-y: auto;
        flex-shrink: 0; /* Prevent sidebar from shrinking */
		box-shadow: var(--shadow-lg);
		color: var(--text-primary);
		gap: var(--space-lg);
		scrollbar-width: thin;
		scrollbar-color: var(--primary-light) var(--bg-sidebar);
	}
	
	.sidebar::-webkit-scrollbar {
		width: 6px;
	}
	
	.sidebar::-webkit-scrollbar-track {
		background: var(--bg-sidebar);
	}
	
	.sidebar::-webkit-scrollbar-thumb {
		background-color: var(--primary-light);
		border-radius: var(--radius-pill);
	}
	
	/* Mobile styles */
    @media (max-width: 768px) {
        .sidebar {
            width: 100%;
            height: auto;
            min-height: 60px;
            max-height: 40vh;
            border-right: none;
            border-bottom: 1px solid var(--input-border);
            padding: var(--space-sm);
			gap: var(--space-md);
        }
        
        h2 {
            font-size: 1.5em;
            margin-bottom: var(--space-xs);
        }
        
        .threads-section {
            margin-bottom: var(--space-sm);
        }
        
        .thread-list {
            max-height: 120px;
        }
        
        .sidebar-section {
            padding-top: var(--space-sm);
            margin-bottom: var(--space-sm);
        }
    }

    h2 {
        text-align: center;
        margin-bottom: var(--space-lg);
        color: var(--text-primary);
		display: flex;
		flex-direction: column;
		align-items: center;
    }
	
	.logo-text {
		background: linear-gradient(135deg, var(--primary-light), var(--secondary));
		-webkit-background-clip: text;
		background-clip: text;
		color: transparent;
		font-size: 1.6em;
		font-weight: bold;
		letter-spacing: 1px;
	}
	
	.subtitle {
		font-size: 0.8em;
		color: var(--text-secondary);
		font-weight: normal;
		margin-top: var(--space-xs);
	}

    .new-chat-button {
        width: 100%;
        padding: var(--space-md);
        margin-bottom: var(--space-md);
        background-color: var(--primary);
        color: white;
        border: none;
        border-radius: var(--radius-md);
        cursor: pointer;
        font-size: 1em;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
		gap: var(--space-sm);
		box-shadow: var(--shadow-sm);
    }
    
    .new-chat-button:hover:not(:disabled) {
        background-color: var(--primary-light);
		transform: translateY(-2px);
		box-shadow: var(--shadow-md);
    }
    
    .new-chat-button:disabled {
        background-color: var(--primary-dark);
        cursor: not-allowed;
		opacity: 0.7;
    }
	
	.btn-icon {
		font-weight: bold;
		font-size: 1.2em;
	}
	
	.sidebar-section {
		border-top: 1px solid var(--input-border);
		padding-top: var(--space-md);
	}

    .thread-list {
        list-style: none;
        padding: 0;
        margin: 0;
        max-height: 200px; /* Limit height */
        overflow-y: auto;
        border: 1px solid var(--input-border);
        border-radius: var(--radius-md);
        background-color: var(--bg-surface);
		scrollbar-width: thin;
		scrollbar-color: var(--primary-light) var(--bg-surface);
    }
	
	.thread-list::-webkit-scrollbar {
		width: 4px;
	}
	
	.thread-list::-webkit-scrollbar-track {
		background: var(--bg-surface);
	}
	
	.thread-list::-webkit-scrollbar-thumb {
		background-color: var(--primary-light);
		border-radius: var(--radius-pill);
	}
	
    .thread-list li {
        border-bottom: 1px solid var(--input-border);
		transition: all 0.2s ease;
    }
	
    .thread-list li:last-child {
        border-bottom: none;
    }
	
    .thread-list li button {
        width: 100%;
        text-align: left;
        padding: var(--space-sm) var(--space-md);
        background: none;
        border: none;
        cursor: pointer;
        font-size: 0.9em;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
		transition: all 0.2s ease;
    }
	
    .thread-list li button:hover:not(:disabled) {
		background-color: var(--bg-elevated);
    }
	
    .thread-list li button:disabled {
		color: var(--text-disabled);
		cursor: not-allowed;
    }
	
    .thread-list li.active {
		background-color: var(--primary-dark);
    }
	
	.thread-list li.active button {
		color: white;
		font-weight: bold;
	}
	
	.empty-list {
		padding: var(--space-md);
		text-align: center;
		color: var(--text-secondary);
		font-style: italic;
	}
	
	.section-icon {
		margin-right: var(--space-xs);
		font-size: 1.1em;
	}

	.mode-switcher {
		margin-bottom: var(--space-md);
	}
	
    .mode-option {
        display: flex;
        align-items: center;
        margin-bottom: var(--space-sm);
        cursor: pointer;
		padding: var(--space-xs) var(--space-sm);
		border-radius: var(--radius-sm);
		transition: all 0.2s ease;
    }
	
	.mode-option:hover {
		background-color: var(--bg-surface);
	}
	
	.mode-option.selected {
		background-color: var(--bg-elevated);
		box-shadow: var(--shadow-sm);
	}
	
    .mode-option input {
		margin-right: var(--space-sm);
		accent-color: var(--primary-light);
    }

    .mode-options {
        flex-grow: 1; /* Takes remaining space */
    }
	
    .mode-options h4 { 
		margin-bottom: var(--space-sm); 
	}

    .mode-info {
        font-size: 0.9em;
        color: var(--text-secondary);
        font-style: italic;
		padding: var(--space-sm);
		background-color: var(--bg-surface);
		border-radius: var(--radius-md);
		border-left: 3px solid var(--primary-light);
    }

    h4 { 
		margin-top: 0; 
		margin-bottom: var(--space-sm); 
		color: var(--text-primary);
		display: flex;
		align-items: center;
	}

    /* Spinner animation */
    .button-spinner {
		border: 3px solid rgba(255, 255, 255, 0.2);
		border-top: 3px solid #fff;
		border-radius: 50%;
		width: 18px;
		height: 18px;
		animation: spin 1s linear infinite;
    }
	
    @keyframes spin {
		0% { transform: rotate(0deg); }
		100% { transform: rotate(360deg); }
	}
</style>

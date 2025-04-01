<script lang="ts">
	import { onMount } from 'svelte'; // Removed duplicate import
	import { slide, fly } from 'svelte/transition'; // Removed fade as it wasn't used after mode removal
	import {
		availableConstitutions, // Keep for potential future use? Or remove if definitely not needed? Let's keep for now.
		availableThreads,
        currentThreadId,
        messages,
        isLoading,
	} from '../stores';
	import { fetchConstitutions, fetchThreads, createNewThread, fetchHistory } from '../api';
    // Removed ConstitutionDropdown and CompareInterface imports

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
            // Removed currentMode.set('chat');
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
    <button class="new-chat-button" on:click={handleNewChat} disabled={$isLoading}>
        {#if $isLoading && !$currentThreadId} 
			<div class="button-spinner"></div>
		{:else} 
			<span class="btn-icon">+</span>
		{/if}
    </button>

    <div class="sidebar-section threads-section">
        <ul class="thread-list">
            {#each $availableThreads as thread, i (thread.thread_id)}
                <li class:active={thread.thread_id === $currentThreadId}>
                    <button on:click={() => loadThread(thread.thread_id)} disabled={$isLoading}>
                        {thread.title || thread.thread_id.substring(0, 8)}
                    </button>
                </li>
            {:else}
                <li class="empty-list">No history yet.</li>
            {/each}
        </ul>
    </div>

    <!-- Mode Switcher and Mode Options sections removed -->

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

    /* Removed h2, .logo-text, and .subtitle styles as they're now in App.svelte */

    .new-chat-button {
		/* Make it a smaller square button */
		width: 40px; 
		height: 40px;
		padding: 0; /* Remove padding */
		margin-bottom: var(--space-md);
		background-color: var(--primary);
		color: white;
		border: none;
		border-radius: var(--radius-md);
		cursor: pointer;
		font-size: 1em; /* Keep font size for icon */
		transition: all 0.3s ease;
		display: flex;
		align-items: center;
		justify-content: center;
		/* Removed gap */
		box-shadow: var(--shadow-sm);
		align-self: flex-end; /* Align to the right */
		flex-shrink: 0; /* Prevent shrinking */
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
	
	.threads-section { /* Target the specific section */
		border-top: 1px solid var(--input-border);
		padding-top: var(--space-md);
		flex-grow: 1; /* Allow this section to grow */
		display: flex; /* Enable flex for children */
		flex-direction: column; /* Stack children vertically */
		min-height: 0; /* Prevent overflow issues in flex */
	}

    .thread-list {
        list-style: none;
        padding: 0;
        margin: 0;
		flex-grow: 1; /* Allow list to fill space in threads-section */
        overflow-y: auto;
        background-color: transparent;
		scrollbar-width: thin;
		scrollbar-color: var(--primary-light) transparent;
        display: block;
    }
	
	.thread-list::-webkit-scrollbar {
		width: 4px;
	}
	
	.thread-list::-webkit-scrollbar-track {
		background: transparent;
	}
	
	.thread-list::-webkit-scrollbar-thumb {
		background-color: var(--primary-light);
		border-radius: var(--radius-pill);
	}
	
    .thread-list li {
        /* Removed border-radius */
		transition: all 0.2s ease;
		/* Removed box-shadow */
		overflow: hidden;
		background-color: var(--bg-surface);
        /* Removed margin-bottom */
        display: block;
        width: 100%;
        border-bottom: 1px solid var(--input-border); /* Add subtle separation */
    }
    
    .thread-list li:last-child {
        border-bottom: none; /* Remove border from last item */
    }
    
    .thread-list li button {
        width: 100%;
        text-align: left;
        padding: 12px 16px; /* Slightly more padding for touch targets */
        background: none;
        border: none;
        cursor: pointer;
        font-size: 0.9em;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
		transition: all 0.2s ease;
		position: relative;
        display: block;
    }
	
    .thread-list li button:hover:not(:disabled) {
		background-color: var(--bg-elevated);
    }
	
    .thread-list li button:disabled {
		color: var(--text-disabled);
		cursor: not-allowed;
    }
	
    .thread-list li.active {
		background-color: var(--primary);
		/* Removed box-shadow */
    }
	
	.thread-list li.active button {
		color: white;
		font-weight: bold;
	}
	
	/* Removed the ::before element with the accent border */
	
	.empty-list {
		padding: 16px;
		text-align: center;
		color: var(--text-secondary);
		font-style: italic;
		background-color: transparent;
		/* Removed border-radius */
		/* Removed border-left */
		margin: 0;
	}

    /* Removed h4 styles since we removed the History heading */

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

<script lang="ts">
    import { onMount, tick } from 'svelte';
    import { slide } from 'svelte/transition';
    import {
        availableThreads,
        currentThreadId,
        isLoading,
    } from '../stores';
    // Removed unused imports: availableConstitutions, messages, activeConstitutionIds
    import { fetchHistory, renameThread } from '../api';
    import { resetForNewChat } from '../stores';

    // State for inline editing
    let editingThreadId: number | null = null;
    let editingName: string = '';
    let renameInput: HTMLInputElement | null = null;

    // Removed onMount data fetching

    function handleNewChat() {
        if ($isLoading) return;
        console.log("Resetting for new chat...");
        resetForNewChat();
    }

    async function loadThread(threadId: number) {
        if ($isLoading || threadId === $currentThreadId) return;
        console.log(`Loading thread ID: ${threadId}`);
        editingThreadId = null;
        try {
            await fetchHistory(threadId);
        } catch (error) {
            console.error(`Failed to load history for thread ID ${threadId}:`, error);
        }
    }

    function startRename(event: MouseEvent, thread: ThreadItem) {
        event.stopPropagation(); // Prevent loadThread if edit button is clicked directly
        if ($isLoading) return;
        editingThreadId = thread.thread_id;
        editingName = thread.name;
        tick().then(() => {
            renameInput?.focus();
            renameInput?.select();
        });
    }

    async function handleRename() {
        if (editingThreadId === null || $isLoading) return;

        const threadIdToRename = editingThreadId;
        const newName = editingName.trim();
        editingThreadId = null; // Exit editing mode

        if (!newName) {
            console.warn("Rename cancelled: name was empty.");
            return;
        }

        const originalThread = $availableThreads.find(t => t.thread_id === threadIdToRename);
        if (originalThread && originalThread.name === newName) {
            console.log("Rename cancelled: name did not change.");
            return;
        }

        console.log(`Attempting to rename thread ${threadIdToRename} to "${newName}"`);
        try {
            await renameThread(threadIdToRename, newName);
            console.log(`Thread ${threadIdToRename} renamed successfully.`);
        } catch (error) {
            console.error(`Failed to rename thread ${threadIdToRename}:`, error);
        }
    }

    function handleRenameKeyDown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            event.preventDefault();
            handleRename();
        } else if (event.key === 'Escape') {
            editingThreadId = null;
        }
    }

</script>

<div class="sidebar">
    <button class="new-chat-button" on:click={handleNewChat} disabled={$isLoading && $currentThreadId === null} title="New Chat">
        {#if $isLoading && $currentThreadId === null}
            <div class="button-spinner"></div>
        {:else}
            <span class="btn-icon">+</span>
        {/if}
    </button>

    <div class="sidebar-section threads-section">
        <ul class="thread-list">
            {#each $availableThreads as thread (thread.thread_id)}
                <li class:active={thread.thread_id === $currentThreadId} class:editing={editingThreadId === thread.thread_id}>
                    {#if editingThreadId === thread.thread_id}
                        <form class="rename-form" on:submit|preventDefault={handleRename}>
                             <input
                                 type="text"
                                 bind:this={renameInput}
                                 bind:value={editingName}
                                 on:blur={handleRename}
                                 on:keydown={handleRenameKeyDown}
                                 disabled={$isLoading}
                                 class="rename-input"
                             />
                         </form>
                    {:else}
                        <div class="thread-item-container" on:click={() => loadThread(thread.thread_id)} role="button" tabindex="0"
                             on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') loadThread(thread.thread_id); }}>
                             <span class="thread-name">{thread.name}</span>
                             <button class="edit-button" title="Rename Thread" on:click={(e) => startRename(e, thread)} disabled={$isLoading}>
                                 ✏️
                             </button>
                        </div>
                    {/if}
                </li>
            {:else}
                <li class="empty-list">No history yet.</li>
            {/each}
        </ul>
    </div>
</div>

<style>
    /* Existing styles ... */
    .sidebar { width: 320px; min-width: 270px; background-color: var(--bg-sidebar); padding: var(--space-lg); display: flex; flex-direction: column; border-right: 1px solid var(--input-border); height: 100%; overflow-y: auto; flex-shrink: 0; box-shadow: var(--shadow-lg); color: var(--text-primary); gap: var(--space-lg); scrollbar-width: thin; scrollbar-color: var(--primary-light) var(--bg-sidebar); }
    .sidebar::-webkit-scrollbar { width: 6px; }
    .sidebar::-webkit-scrollbar-track { background: var(--bg-sidebar); }
    .sidebar::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }

    .new-chat-button { width: 40px; height: 40px; padding: 0; margin-bottom: var(--space-md); background-color: var(--primary); color: white; border: none; border-radius: var(--radius-md); cursor: pointer; font-size: 1em; transition: all 0.3s ease; display: flex; align-items: center; justify-content: center; box-shadow: var(--shadow-sm); align-self: flex-end; flex-shrink: 0; }
    .new-chat-button:hover:not(:disabled) { background-color: var(--primary-light); transform: translateY(-2px); box-shadow: var(--shadow-md); }
    .new-chat-button:disabled { background-color: var(--primary-dark); cursor: not-allowed; opacity: 0.7; }
    .btn-icon { font-weight: bold; font-size: 1.2em; }

    .threads-section { border-top: 1px solid var(--input-border); padding-top: var(--space-md); flex-grow: 1; display: flex; flex-direction: column; min-height: 0; }

    .thread-list { list-style: none; padding: 0; margin: 0; flex-grow: 1; overflow-y: auto; background-color: transparent; scrollbar-width: thin; scrollbar-color: var(--primary-light) transparent; display: block; }
    .thread-list::-webkit-scrollbar { width: 4px; }
    .thread-list::-webkit-scrollbar-track { background: transparent; }
    .thread-list::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }

    .thread-list li {
        transition: background-color 0.2s ease; /* Simplified transition */
        overflow: hidden;
        background-color: var(--bg-surface);
        display: flex;
        align-items: center;
        width: 100%;
        border-bottom: 1px solid var(--input-border);
        position: relative; /* For potential absolute positioning inside if needed */
    }
    .thread-list li:last-child { border-bottom: none; }
    .thread-list li.editing { background-color: var(--bg-elevated); }

    /* --- NEW: Clickable container for non-edit mode --- */
    .thread-item-container {
        flex-grow: 1;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px; /* Apply padding here */
        cursor: pointer;
        transition: background-color 0.2s ease;
    }
    .thread-item-container:hover {
        background-color: var(--bg-elevated);
    }
    .thread-list li.active .thread-item-container {
        background-color: var(--primary); /* Apply active background here */
        color: white; /* Apply active text color here */
    }
     .thread-list li.active .thread-item-container .thread-name {
          font-weight: bold; /* Bold active thread name */
     }
     .thread-list li.active .thread-item-container .edit-button {
          color: white; /* Ensure edit button contrasts on active */
          opacity: 1; /* Ensure edit button visible on active */
      }


    .rename-form { width: 100%; display: flex; }
    .rename-input {
         flex-grow: 1; padding: 12px 16px; font-size: 0.9em; border: none; /* Removed border */
         background-color: transparent; /* Use li background */
         color: var(--text-primary); border-radius: 0; outline: none;
         border: 1px solid var(--primary); /* Add border only for input */
     }
    .rename-input:focus { box-shadow: 0 0 0 2px var(--primary-light); }

    .thread-name {
         overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
         padding-right: 5px;
         flex-grow: 1; /* Allow name to take available space */
         /* Inherit color from parent (.thread-item-container) */
     }

    .edit-button {
         background: none; border: none; cursor: pointer; padding: 4px;
         margin-left: 8px; color: var(--text-secondary); font-size: 0.8em;
         line-height: 1; border-radius: var(--radius-sm); flex-shrink: 0;
         opacity: 0; /* Hidden by default */
         transition: opacity 0.2s ease, background-color 0.2s ease, color 0.2s ease;
         z-index: 1; /* Ensure button is clickable over container hover */
     }
    /* Show edit button on hover of the LIST ITEM */
    .thread-list li:hover .edit-button {
         opacity: 1;
    }
    .edit-button:hover { background-color: var(--primary-light); color: white; }
    .edit-button:disabled { opacity: 0.3 !important; cursor: not-allowed; } /* Use !important to override hover opacity */

    .empty-list { padding: 16px; text-align: center; color: var(--text-secondary); font-style: italic; background-color: transparent; margin: 0; display: block; border-bottom: none; }

    .button-spinner { border: 3px solid rgba(255, 255, 255, 0.2); border-top: 3px solid #fff; border-radius: 50%; width: 18px; height: 18px; animation: spin 1s linear infinite; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

    @media (max-width: 768px) { /* Existing mobile styles */ }
</style>
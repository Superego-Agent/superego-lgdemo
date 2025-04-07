<script lang="ts">
    import { tick } from 'svelte';
    import { get } from 'svelte/store';
    import { slide } from 'svelte/transition';
    import { isLoading, activeConversationId, resetForNewChat } from '../stores';
    import { managedConversations, updateConversation, deleteConversation } from '../conversationManager'; // Import deleteConversation
    import type { ConversationMetadata } from '../conversationManager';

    // Import icons
    import IconEdit from '~icons/fluent/edit-24-regular';
    import IconDelete from '~icons/fluent/delete-24-regular';
    import IconAdd from '~icons/fluent/add-24-regular';

    // State for inline editing
    let editingConversationId: string | null = null; // Changed from number to string ID
    let editingName: string = '';
    let renameInput: HTMLInputElement | null = null;

    function handleNewChat() {
        if ($isLoading && $activeConversationId === null) return; // Prevent multiple rapid clicks if already creating
        console.log("Resetting for new chat...");
        resetForNewChat(); // This now creates a new entry and sets it active
    }

    // Renamed from loadThread - only sets the active conversation ID
    function selectConversation(conversationId: string) {
        if ($isLoading || conversationId === $activeConversationId) return;
        console.log(`Selecting conversation ID: ${conversationId}`);
        editingConversationId = null; // Exit editing mode if selecting a different chat
        activeConversationId.set(conversationId);
        // Fetching history should now be triggered by a component observing activeThreadId changes
    }

    function startRename(event: MouseEvent, conversation: ConversationMetadata) {
        event.stopPropagation(); // Prevent selectConversation if edit button is clicked directly
        if ($isLoading) return;
        editingConversationId = conversation.id;
        editingName = conversation.name;
        tick().then(() => {
            renameInput?.focus();
            renameInput?.select();
        });
    }

    // Renaming now updates localStorage via conversationManager
    function handleRename() {
        if (editingConversationId === null || $isLoading) return;

        const conversationIdToRename = editingConversationId;
        const newName = editingName.trim();
        editingConversationId = null; // Exit editing mode

        if (!newName) {
            console.warn("Rename cancelled: name was empty.");
            return;
        }

        // Find original name directly from the store using get()
        const currentConversations = get(managedConversations);
        const originalConv = currentConversations.find(c => c.id === conversationIdToRename);
        const originalName = originalConv?.name ?? '';

        if (originalName === newName) {
            console.log("Rename cancelled: name did not change.");
            return;
        }

        console.log(`Attempting to rename conversation ${conversationIdToRename} to "${newName}" (client-side)`);
        try {
            // Update using the conversationManager function
            updateConversation(conversationIdToRename, { name: newName });
            console.log(`Conversation ${conversationIdToRename} renamed successfully in localStorage.`);
        } catch (error) {
            // This catch might not be effective if updateConversation doesn't throw
            console.error(`Failed to rename conversation ${conversationIdToRename}:`, error);
            // TODO: Add user feedback for rename failure?
        }
    }

    function handleRenameKeyDown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            event.preventDefault();
            handleRename();
        } else if (event.key === 'Escape') {
            editingConversationId = null; // Cancel edit on Escape
        }
    }

    // Function to handle deleting a conversation
    function handleDelete(event: MouseEvent, conversationId: string) {
        event.stopPropagation(); // Prevent selectConversation
        if ($isLoading) return;

        // Optional: Add a confirmation dialog here
        if (confirm(`Are you sure you want to delete this conversation?`)) {
            console.log(`Attempting to delete conversation ${conversationId} (client-side)`);
            try {
                deleteConversation(conversationId);
                console.log(`Conversation ${conversationId} deleted successfully from localStorage.`);
                // If the deleted conversation was the active one, reset to new chat state
                if ($activeConversationId === conversationId) {
                    resetForNewChat();
                }
            } catch (error) {
                console.error(`Failed to delete conversation ${conversationId}:`, error);
                // TODO: Add user feedback for delete failure?
            }
        }
    }
</script>

<div class="sidebar">
    <button class="new-chat-button" on:click={handleNewChat} disabled={$isLoading && $activeConversationId === null} title="New Chat">
        {#if $isLoading && $activeConversationId === null}
            <div class="button-spinner"></div>
            <span>Creating...</span>
        {:else}
            <IconAdd class="btn-icon" />
            <span>New Chat</span>
        {/if}
    </button>

    <div class="sidebar-section threads-section">
        <ul class="thread-list">
            {#each $managedConversations as conversation (conversation.id)} 
                <li class:active={conversation.id === $activeConversationId} class:editing={editingConversationId === conversation.id}> 
                    {#if editingConversationId === conversation.id} 
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
                        <div class="thread-item-container" on:click={() => selectConversation(conversation.id)} role="button" tabindex="0"
                             on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') selectConversation(conversation.id); }}>
                            <span class="thread-name">{conversation.name}</span>
                            <div class="thread-actions">
                                <button class="icon-button edit-button" title="Rename Conversation" on:click={(e) => startRename(e, conversation)} disabled={$isLoading}>
                                    <IconEdit />
                                </button>
                                <button class="icon-button delete-button" title="Delete Conversation" on:click={(e) => handleDelete(e, conversation.id)} disabled={$isLoading}>
                                    <IconDelete />
                                </button>
                            </div>
                        </div>
                    {/if}
                </li>
            {:else}
                <li class="empty-list">No conversations yet.</li>
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

    /* Updated New Chat Button styles */
    .new-chat-button {
        width: 100%; /* Full width */
        height: 40px;
        padding: 0 var(--space-md); /* Add horizontal padding */
        margin-bottom: var(--space-sm); /* Reduced margin */
        background-color: var(--primary);
        color: white;
        border: none;
        border-radius: var(--radius-md);
        cursor: pointer;
        font-size: 0.9em; /* Slightly smaller font */
        font-weight: 500;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center; /* Center content */
        gap: var(--space-xs); /* Space between icon and text */
        box-shadow: var(--shadow-sm);
        flex-shrink: 0;
    }
    .new-chat-button:hover:not(:disabled) { background-color: var(--primary-light); box-shadow: var(--shadow-md); }
    .new-chat-button:disabled { background-color: var(--primary-dark); cursor: not-allowed; opacity: 0.7; }
    .btn-icon { font-size: 1.3em; /* Adjust icon size if needed */ display: flex; align-items: center; justify-content: center; }

    /* Remove top border and reduce padding */
    .threads-section { padding-top: 0; /* Removed padding */ flex-grow: 1; display: flex; flex-direction: column; min-height: 0; }

    .thread-list { list-style: none; padding: 0; margin: 0; flex-grow: 1; overflow-y: auto; background-color: transparent; scrollbar-width: thin; scrollbar-color: var(--primary-light) transparent; display: block; }
    .thread-list::-webkit-scrollbar { width: 4px; }
    .thread-list::-webkit-scrollbar-track { background: transparent; }
    .thread-list::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }

    /* Remove background and border from list items */
    .thread-list li {
        overflow: hidden;
        display: flex;
        align-items: center;
        width: 100%;
        position: relative; /* For potential absolute positioning inside if needed */
    }
    /* Remove last-child rule as border is gone */
    .thread-list li.editing { background-color: var(--bg-elevated); /* Keep editing distinct */ }

    /* --- NEW: Clickable container for non-edit mode --- */
    .thread-item-container {
        flex-grow: 1;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px; /* Keep padding on container */
        cursor: pointer;
        transition: background-color 0.2s ease;
        border-radius: var(--radius-md); /* Add slight rounding to hover/active states */
        margin: 2px 0; /* Add small vertical margin between items */
    }
    .thread-item-container:hover {
        background-color: var(--bg-elevated); /* Keep hover effect */
    }
    .thread-list li.active .thread-item-container {
        background-color: var(--primary); /* Keep active background */
        color: white; /* Keep active text color */
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

    /* --- NEW: Styles for icon buttons --- */
    .thread-actions {
        display: flex;
        align-items: center;
        gap: 4px; /* Space between icons */
        flex-shrink: 0;
        margin-left: 8px;
    }

    .icon-button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        color: var(--text-secondary);
        font-size: 1.1em; /* Adjust size as needed */
        line-height: 1;
        border-radius: var(--radius-sm);
        opacity: 0; /* Hidden by default */
        transition: opacity 0.2s ease, background-color 0.2s ease, color 0.2s ease;
        display: flex; /* Helps center icon if needed */
        align-items: center;
        justify-content: center;
        z-index: 1; /* Ensure button is clickable over container hover */
    }

    /* Show buttons on hover of the LIST ITEM */
    .thread-list li:hover .icon-button {
        opacity: 1;
    }
     /* Keep buttons visible on active item */
     .thread-list li.active .icon-button {
         opacity: 1;
         color: white; /* Ensure icons contrast on active background */
     }

    .icon-button:hover:not(:disabled) {
        background-color: var(--primary-light);
        color: white;
    }
    .icon-button:disabled {
        opacity: 0.3 !important; /* Use !important to override hover opacity */
        cursor: not-allowed;
    }

    /* Specific color for delete button hover */
    .delete-button:hover:not(:disabled) {
        background-color: var(--error); /* Use error color for delete hover */
        color: white;
    }
</style>

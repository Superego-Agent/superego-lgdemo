<script lang="ts">
    import { tick } from 'svelte';
    import { get } from 'svelte/store';
    import { slide } from 'svelte/transition';
    import { activeConversationId, conversationStates, updateConversationMetadataState } from '../stores';
    import { managedConversations, deleteConversation } from '../conversationManager';
    import type { ConversationMetadata } from '../conversationManager';
    import { deleteThread } from '../api';

    import IconEdit from '~icons/fluent/edit-24-regular';
    import IconDelete from '~icons/fluent/delete-24-regular';
    import IconAdd from '~icons/fluent/add-24-regular';

    let editingConversationId: string | null = null;
    let editingName: string = '';
    let originalEditingName: string = '';
    let renameInput: HTMLInputElement | null = null;

    $: isActiveConversationProcessing = $activeConversationId ? ($conversationStates[$activeConversationId]?.status === 'loading_history' || $conversationStates[$activeConversationId]?.status === 'streaming') : false;

    function handleNewChat() {
        if (isActiveConversationProcessing && $activeConversationId === null) return;
        activeConversationId.set(null);
    }

    function selectConversation(conversationId: string) {
        if (conversationId === $activeConversationId) return;
        editingConversationId = null;
        activeConversationId.set(conversationId);
    }

    function startRename(event: MouseEvent, conversation: ConversationMetadata) {
        event.stopPropagation();
        editingConversationId = conversation.id;
        editingName = conversation.name;
        originalEditingName = conversation.name;
        tick().then(() => {
            renameInput?.focus();
            renameInput?.select();
        });
    }

    function handleRename() {
        if (editingConversationId === null) return;

        const conversationIdToRename = editingConversationId;
        const newName = editingName.trim();
        const originalName = originalEditingName;

        editingConversationId = null;

        if (!newName || newName === originalName) {
            return;
        }

        try {
            managedConversations.update(list =>
                list.map(conv =>
                    conv.id === conversationIdToRename ? { ...conv, name: newName, last_updated_at: new Date().toISOString() } : conv
                ).sort((a, b) => new Date(b.last_updated_at).getTime() - new Date(a.last_updated_at).getTime())
            );
            updateConversationMetadataState(conversationIdToRename, { name: newName });
        } catch (error) {
            console.error(`Failed to rename conversation ${conversationIdToRename}:`, error);
            // TODO: Add user feedback for rename failure (e.g., globalError store)
        }
    }

    function handleRenameKeyDown(event: KeyboardEvent) {
        if (event.key === 'Enter') {
            event.preventDefault();
            handleRename();
        } else if (event.key === 'Escape') {
            editingConversationId = null;
        }
    }

    async function handleDelete(event: MouseEvent, conversationId: string) {
        event.stopPropagation();

        const conversationToDelete = get(managedConversations).find(c => c.id === conversationId);
        if (!conversationToDelete) return;

        if (!confirm(`Are you sure you want to delete conversation "${conversationToDelete.name}"?`)) {
            return;
        }

        const wasActive = ($activeConversationId === conversationId);

        try {
            if (conversationToDelete.thread_id) {
                await deleteThread(conversationToDelete.thread_id);
            }

            deleteConversation(conversationId);

            conversationStates.update(s => {
                delete s[conversationId];
                return s;
            });

            if (wasActive) {
                activeConversationId.set(null);
            }
        } catch (error: unknown) {
            console.error(`Failed to delete conversation ${conversationId}:`, error);
            // TODO: Add user feedback for delete failure (e.g., globalError store)
        }
    }
</script>

<div class="sidebar">
    <button class="new-chat-button" on:click={handleNewChat} disabled={isActiveConversationProcessing && $activeConversationId === null} title="New Thread">
        {#if isActiveConversationProcessing && $activeConversationId === null}
            <div class="button-spinner"></div>
            <span>Creating...</span>
        {:else}
            <IconAdd class="btn-icon" />
            <span>New Thread</span>
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
                                 disabled={false}
                                class="rename-input"
                            />
                        </form>
                    {:else}
                        <div class="thread-item-container" on:click={() => selectConversation(conversation.id)} role="button" tabindex="0"
                             on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') selectConversation(conversation.id); }}>
                            <span class="thread-name">{conversation.name}</span>
                            <div class="thread-actions">
                                <button class="icon-button" title="Rename Conversation" on:click={(e) => startRename(e, conversation)} disabled={false}>
                                    <IconEdit />
                                </button>
                                <button class="icon-button delete-button" title="Delete Conversation" on:click={(e) => handleDelete(e, conversation.id)} disabled={false}>
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

<style lang="scss">
    @use '../styles/mixins' as *;

    .sidebar {
        width: 320px;
        min-width: 270px;
        background-color: var(--bg-sidebar);
        padding: var(--space-lg);
        display: flex;
        flex-direction: column;
        border-right: 1px solid var(--input-border);
        height: 100%;
        overflow-y: auto;
        flex-shrink: 0;
        box-shadow: var(--shadow-lg);
        color: var(--text-primary);
        gap: var(--space-lg);
        @include custom-scrollbar($track-bg: var(--bg-sidebar), $thumb-bg: var(--primary-light), $width: 6px); // Use mixin
    }

    .new-chat-button {
        width: 100%;
        height: 40px;
        padding: 0 var(--space-md);
        margin-bottom: var(--space-sm);
        background-color: var(--primary);
        color: white;
        border: none;
        border-radius: var(--radius-md);
        cursor: pointer;
        font-size: 0.9em;
        font-weight: 500;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-xs);
        box-shadow: var(--shadow-sm);
        flex-shrink: 0;

        &:hover:not(:disabled) {
            background-color: var(--primary-light);
            box-shadow: var(--shadow-md);
        }
        &:disabled {
            background-color: var(--primary-dark);
            cursor: not-allowed;
            opacity: 0.7;
        }

        .btn-icon {
            font-size: 1.3em;
            display: flex;
            align-items: center;
            justify-content: center;
        }
    }

    .threads-section {
        padding-top: 0;
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        min-height: 0;
    }

    .thread-list {
        list-style: none;
        padding: 0;
        margin: 0;
        flex-grow: 1;
        overflow-y: auto;
        background-color: transparent;
        @include custom-scrollbar($track-bg: transparent, $thumb-bg: var(--primary-light), $width: 4px); // Use mixin
        display: block;

        li {
            overflow: hidden;
            display: flex;
            align-items: center;
            width: 100%;
            position: relative;

            &.editing {
                background-color: var(--bg-elevated);
            }

            // Show action buttons on hover of the list item
            &:hover .thread-actions .icon-button {
                opacity: 1;
            }

            &.active {
                .thread-item-container {
                    background-color: var(--primary);
                    color: white;

                    .thread-name {
                        font-weight: bold;
                    }
                    // Ensure buttons are visible and contrast on active item
                    .icon-button {
                        color: white;
                        opacity: 1;
                    }
                }
            }
        }
    }

    .thread-item-container {
        flex-grow: 1;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        cursor: pointer;
        transition: background-color 0.2s ease;
        border-radius: var(--radius-md);
        margin: 2px 0;
        overflow: hidden; // Add this to clip overflowing content (like pushed buttons)

        &:hover {
            background-color: var(--bg-elevated);
        }

        .thread-name {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            padding-right: 5px;
            flex-grow: 1;
            min-width: 0; // Add this to ensure ellipsis works correctly in flex context
        }

        .thread-actions {
            display: flex;
            align-items: center;
            gap: 4px;
            flex-shrink: 0;
            margin-left: 8px;
        }
    }

    .rename-form {
        width: 100%;
        display: flex;
    }

    .rename-input {
        flex-grow: 1;
        padding: 12px 16px;
        font-size: 0.9em;
        border: 1px solid var(--primary);
        background-color: transparent;
        color: var(--text-primary);
        border-radius: 0; // Keep sharp edges for input within list item
        outline: none;

        &:focus {
            box-shadow: 0 0 0 2px var(--primary-light);
        }
    }

    .icon-button {
        background: none;
        border: none;
        cursor: pointer;
        padding: 4px;
        color: var(--text-secondary);
        line-height: 1;
        border-radius: var(--radius-sm);
        opacity: 0;
        transition: opacity 0.2s ease, background-color 0.2s ease, color 0.2s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-size: 1.1em; 

        &:hover:not(:disabled) {
            background-color: var(--primary-light);
            color: white;
        }
        &:disabled {
            opacity: 0.3; 
            cursor: not-allowed;
        }
    }

    /* Specific hover for delete button */
    .delete-button:hover:not(:disabled) {
        background-color: var(--error);
        color: white;
    }

    .empty-list {
        padding: 16px;
        text-align: center;
        color: var(--text-secondary);
        font-style: italic;
        background-color: transparent;
        margin: 0;
        display: block;
        border-bottom: none;
    }

    .button-spinner {
        @include loading-spinner($size: 18px, $color: #fff, $track-color: rgba(255, 255, 255, 0.2));
    }

    @media (max-width: 768px) {
        /* Mobile styles can be added here if needed */
    }
</style>

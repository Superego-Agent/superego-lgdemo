<script lang="ts">
    // Import stores - removed messages, isLoading; added conversationStates
    import {
        globalError,
        activeConversationId,
        availableConstitutions,
        constitutionAdherenceLevels,
        conversationStates // Import the main state store
    } from '../stores';
    import { streamRun } from '../api'; // fetchHistory is no longer called directly from here
    import { get } from 'svelte/store';
    // Import conversation manager store for metadata lookup if needed
    import { managedConversations } from '../conversationManager';
    import { formatAdherenceLevelsForApi } from '../utils';
    import MessageCard from './MessageCard.svelte';
    import ChatInput from './ChatInput.svelte';
    import ConstitutionSelector from './ConstitutionSelector.svelte';
    // Removed onMount, onDestroy, tick - no longer needed for history loading here
    import { afterUpdate } from 'svelte';
    import { slide, fade } from 'svelte/transition';
    import { nanoid } from 'nanoid';

    let chatContainer: HTMLElement;
    let isAtBottom = true;

    // --- Auto-scroll Logic (remains the same) ---
    function checkScroll() {
        if (chatContainer) {
            const threshold = 50;
            isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < threshold;
        }
    }
    afterUpdate(() => {
        if (chatContainer && isAtBottom) {
            requestAnimationFrame(() => {
                 chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
            });
        }
    });

    // --- Reactive State Derivations ---
    $: activeState = $activeConversationId ? $conversationStates[$activeConversationId] : null;
    $: displayedMessages = activeState?.messages ?? [];
    $: currentStatus = activeState?.status ?? 'idle'; // Default to idle if no active state
    $: currentError = activeState?.error;
    $: isProcessing = currentStatus === 'loading_history' || currentStatus === 'streaming';

    // --- Message Sending Logic ---
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        // Disable sending if currently processing the active conversation OR if input is empty
        if (!userInput || isProcessing) {
            console.log(`Send cancelled: Input empty (${!userInput}), or processing (${isProcessing})`);
            return;
        }

        const currentActiveClientId = get(activeConversationId); // Can be null if starting a new chat

        // Optimistic update: Add user message to the correct conversation state
        const userMessage: HumanMessage = {
            id: nanoid(8),
            sender: 'human',
            content: userInput,
            timestamp: Date.now()
        };

        // If starting a new chat, the streamRun call will handle creating the state entry
        // If adding to existing, update the state store
        if (currentActiveClientId) {
             conversationStates.update(s => {
                 if (s[currentActiveClientId]) {
                     s[currentActiveClientId].messages.push(userMessage);
                 } else {
                     // This case should be rare if UI prevents sending before state exists
                     console.warn(`Optimistic update failed: State for client ID ${currentActiveClientId} not found.`);
                 }
                 return s;
             });
        }
        // Note: For a truly new chat (activeId is null), the optimistic update won't happen here.
        // streamRun will create the state and add the message upon receiving thread_created.
        // This could be improved by having streamRun return the new clientId immediately,
        // allowing optimistic update even for the very first message. For now, we accept this minor delay.


        // Format adherence levels 
        const levels = $constitutionAdherenceLevels;
        const activeIds = Object.keys(levels);
        const adherenceLevelsText = formatAdherenceLevelsForApi(levels, $availableConstitutions);

        console.log(`Sending message for Client ID: ${currentActiveClientId ?? 'NEW CHAT'} with constitutions: ${activeIds.join(', ') || 'none'}`);
        console.log(`Adherence Levels Payload:\n${adherenceLevelsText || '(None)'}`);

        try {
            // Call streamRun, passing the current *client* ID (null if new chat)
            await streamRun(userInput, currentActiveClientId, activeIds, adherenceLevelsText);
        } catch (error: unknown) {
            console.error("Error during streamRun call:", error);
            globalError.set(`Failed to send message: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

</script>

<div class="chat-interface">
    {#if $globalError}
        <div class="error-banner" transition:slide={{ duration: 300 }}>
             <div class="error-content">
                 <span class="error-icon">⚠️</span>
                 <span>Error: {$globalError}</span>
             </div>
         </div>
    {/if}

    <div class="messages-container" bind:this={chatContainer} on:scroll={checkScroll}>
        {#each displayedMessages as message (message.id)}
             <div transition:fade={{ duration: 300 }}>
                  <MessageCard {message} />
             </div>
        {:else}
            {#if currentStatus === 'loading_history'}
                 <div class="loading-indicator">
                      <div class="spinner"></div>
                      <span>Loading History...</span>
                  </div>
            {:else if currentStatus === 'error'}
                 <div class="empty-chat error-message" transition:fade={{ duration: 500 }}>
                      <div class="empty-chat-icon">⚠️</div>
                      <p>Error loading conversation:</p>
                      <p><small>{currentError || 'Unknown error'}</small></p>
                  </div>
            {:else if !$activeConversationId}
                 <div class="empty-chat" transition:fade={{ duration: 500 }}>
                      <div class="empty-chat-icon">💬</div>
                      <p>Select a conversation or start a new one.</p>
                      <p><small>(Select constitution(s) below before sending first message)</small></p>
                  </div>
             {:else}
                  <div class="empty-chat" transition:fade={{ duration: 500 }}>
                       <div class="empty-chat-icon">💬</div>
                       <p>Send a message to start the chat.</p>
                   </div>
            {/if}
        {/each}

        {#if currentStatus === 'streaming'}
            <div class="loading-indicator">
                  <div class="spinner"></div>
                  <span>Thinking...</span>
              </div>
        {/if}
    </div>

    <div class="input-area">
         <ConstitutionSelector /> 
        <ChatInput on:send={handleSend} disabled={isProcessing} />
    </div>
</div>

<style lang="scss">
    @use '../styles/mixins' as *;

    .chat-interface {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        height: 100%;
        overflow: hidden;
        background-color: var(--bg-primary);
        width: 100%;
        position: relative;
    }
    .error-banner {
        background-color: var(--error-bg);
        color: var(--error);
        padding: var(--space-md);
        border-bottom: 1px solid var(--error);
        text-align: center;
        font-size: 0.9em;
        box-shadow: var(--shadow-md);
        flex-shrink: 0;
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
        -webkit-overflow-scrolling: touch;
        @include custom-scrollbar();
    }
    .empty-chat {
        text-align: center;
        color: var(--text-secondary);
        margin: auto 0; /* Center vertically within container */
        padding: var(--space-xl) 0;
        font-style: italic;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--space-sm); /* Reduced gap */
    }
     .empty-chat.error-message {
         color: var(--error);
         font-style: normal;
         p { margin: 0; }
         small { color: var(--text-secondary); }
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
        @include loading-spinner(); 
    }

    .input-area {
        padding: var(--space-sm) var(--space-lg) var(--space-md);
        border-top: 1px solid var(--input-border);
        background-color: var(--bg-primary); 
        flex-shrink: 0;
         display: flex;
         flex-direction: column;
         gap: var(--space-sm); 
    }

     @media (max-width: 768px) { /* ... existing mobile styles ... */ }
</style>

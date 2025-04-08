<script lang="ts">
    import {
        globalError,
        activeConversationId,
        availableConstitutions,
        constitutionAdherenceLevels,
        conversationStates
    } from '../stores';
    import { streamRun } from '../api';
    import { get } from 'svelte/store';
    import { managedConversations } from '../conversationManager';
    import { formatAdherenceLevelsForApi } from '../utils';
    import MessageCard from './MessageCard.svelte';
    import ChatInput from './ChatInput.svelte';
    import ConstitutionSelector from './ConstitutionSelector.svelte';
    import { afterUpdate } from 'svelte';
    import { slide, fade } from 'svelte/transition';
    import { nanoid } from 'nanoid';
    import ErrorIcon from '~icons/fluent/warning-24-regular';
    import ChatIcon from '~icons/fluent/chat-24-regular'; // Import chat icon

    let chatContainer: HTMLElement;
    let isAtBottom = true;

    // Auto-scroll Logic
    function checkScroll() {
        if (chatContainer) {
            const threshold = 50; // Pixels from bottom to trigger staying scrolled
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

    // Reactive State Derivations from Stores
    $: activeState = $activeConversationId ? $conversationStates[$activeConversationId] : null;
    $: displayedMessages = activeState?.messages ?? [];
    $: currentStatus = activeState?.status ?? 'idle';
    $: currentError = activeState?.error;
    $: isProcessing = currentStatus === 'loading_history' || currentStatus === 'streaming'; // Input disabled during these states

    // Message Sending Logic
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        if (!userInput || isProcessing) {
            return; // Prevent sending empty messages or while processing
        }

        const currentActiveClientId = get(activeConversationId);

        // Optimistic update: Add user message immediately to the UI
        const userMessage: HumanMessage = {
            id: nanoid(8), // Generate a temporary client-side ID
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
        // Format adherence levels for the API call
        const levels = $constitutionAdherenceLevels;
        const activeIds = Object.keys(levels);
        const adherenceLevelsText = formatAdherenceLevelsForApi(levels, $availableConstitutions);

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
                 <span class="error-icon"><ErrorIcon /></span>
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
                      <div class="empty-chat-icon"><ErrorIcon /></div>
                      <p>Error loading conversation:</p>
                      <p><small>{currentError || 'Unknown error'}</small></p>
                  </div>
            {:else if !$activeConversationId}
                 <div class="empty-chat" transition:fade={{ duration: 500 }}>
                      <div class="empty-chat-icon"><ChatIcon /></div>
                      <p>Select or start a thread</p>
                      <p><small>(Select constitution(s) for the 'Superego' agent first)</small></p>
                  </div>
             {:else}
                  <div class="empty-chat" transition:fade={{ duration: 500 }}>
                       <div class="empty-chat-icon"><ChatIcon /></div>
                       <p>Send a message to start the run.</p>
                   </div>
            {/if}
        {/each}

        {#if currentStatus === 'streaming'}
            <div class="loading-indicator">
                  <div class="spinner"></div>
                  <span>Running...</span>
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
        gap: var(--space-sm);
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
 </style>

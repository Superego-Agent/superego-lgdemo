<script lang="ts">
    import { messages, isLoading, globalError, currentThreadId, activeConstitutionIds } from '../stores';
    import { streamRun } from '../api';
    import MessageCard from './MessageCard.svelte';
    import ChatInput from './ChatInput.svelte';
    import ConstitutionSelector from './ConstitutionSelector.svelte';
    import { afterUpdate, onMount } from 'svelte'; // Added onMount
    import { slide, fade } from 'svelte/transition';
    import { nanoid } from 'nanoid'; // Import nanoid for unique IDs

    let chatContainer: HTMLElement;
    let isAtBottom = true;
    let isConstitutionSelectorVisible = false; // State for collapsible selector

    // --- Auto-scroll Logic ---
    function checkScroll() { /* ... (no changes) ... */
        if (chatContainer) {
            const threshold = 50; // Pixels from bottom
            isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < threshold;
        }
    }
    afterUpdate(() => { /* ... (no changes) ... */
        if (chatContainer && isAtBottom) {
            setTimeout(() => {
                chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
            }, 0);
        }
    });

    // --- Initialize constitution visibility ---
    // Auto-expand on new chat (when component mounts and currentThreadId is null)
    onMount(() => {
        isConstitutionSelectorVisible = ($currentThreadId === null);
    });
    // Also reactively set visibility if thread ID changes back to null (e.g., "New Chat" clicked)
    $: if ($currentThreadId === null && !isConstitutionSelectorVisible) {
         isConstitutionSelectorVisible = true;
    }


    // --- Message Sending Logic ---
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        if (!userInput || $isLoading) {
            console.log("Send cancelled: input empty or already loading.");
            return;
        }

        // --- FIX: Optimistically add user message ---
        const userMessage: HumanMessage = {
            // Use nanoid for a more robust temporary unique ID
            id: nanoid(8), // Generate short unique ID
            sender: 'human',
            content: userInput,
            timestamp: Date.now()
            // node, set_id typically not set for human input
        };
        messages.update(msgs => [...msgs, userMessage]);
        // --- End Fix ---

        // Get current state from stores
        const threadId = $currentThreadId; // Can be number or null
        const constitutionIds = $activeConstitutionIds; // Array of strings

        console.log(`Sending message to thread ${threadId === null ? 'NEW' : threadId} with constitutions: ${constitutionIds.join(', ')}`);

        try {
            await streamRun(userInput, threadId, constitutionIds);
            // Stream handles AI responses, end event updates threadId if new
        } catch (error) {
            console.error("Error starting streamRun:", error);
            // Optionally remove the optimistic user message if the stream fails immediately
            // messages.update(msgs => msgs.filter(m => m.id !== userMessage.id));
            // Error display is handled globally by api.ts
        }
    }

    function toggleConstitutionSelector() {
        isConstitutionSelectorVisible = !isConstitutionSelectorVisible;
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
        {#each $messages as message (message.id)}
             <div transition:fade={{ duration: 300 }} key={message.id}>
                  <MessageCard {message} />
             </div>
        {:else}
            <div class="empty-chat" transition:fade={{ duration: 500 }}>
                <div class="empty-chat-icon">💬</div>
                <p>Select constitution(s) and send a message</p>
            </div>
        {/each}

        {#if $isLoading}
            <div class="loading-indicator">
                  <div class="spinner"></div>
                  <span>Thinking...</span>
              </div>
        {/if}
    </div>

    <div class="input-area">
         <div class="constitution-toggle-area">
              <button class="toggle-button" on:click={toggleConstitutionSelector} title={isConstitutionSelectorVisible ? 'Hide Constitutions' : 'Show Constitutions'}>
                   <span>Constitutions</span>
                   <span class="toggle-icon" class:rotated={isConstitutionSelectorVisible}>▼</span>
              </button>
         </div>
         {#if isConstitutionSelectorVisible}
              <div class="selector-wrapper" transition:slide|local={{duration: 200}}>
                   <ConstitutionSelector />
              </div>
         {/if}
        <ChatInput on:send={handleSend} disabled={$isLoading} />
    </div>
</div>

<style>
    /* Existing styles ... */
    .chat-interface { flex-grow: 1; display: flex; flex-direction: column; height: 100%; overflow: hidden; background-color: var(--bg-primary); width: 100%; position: relative; }
    .error-banner { background-color: var(--error-bg); color: var(--error); padding: var(--space-md); border-bottom: 1px solid var(--error); text-align: center; font-size: 0.9em; box-shadow: var(--shadow-md); flex-shrink: 0; }
    .error-content { display: flex; align-items: center; justify-content: center; gap: var(--space-sm); }
    .error-icon { font-size: 1.2em; }
    .messages-container { flex-grow: 1; overflow-y: auto; padding: var(--space-lg); display: flex; flex-direction: column; gap: var(--space-md); -webkit-overflow-scrolling: touch; scrollbar-width: thin; scrollbar-color: var(--primary-light) var(--bg-surface); }
    .messages-container::-webkit-scrollbar { width: 8px; }
    .messages-container::-webkit-scrollbar-track { background: var(--bg-surface); border-radius: var(--radius-pill); }
    .messages-container::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }
    .empty-chat { text-align: center; color: var(--text-secondary); margin: auto; font-style: italic; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-md); }
    .empty-chat-icon { font-size: 2.5em; margin-bottom: var(--space-sm); opacity: 0.7; }
    .loading-indicator { display: flex; align-items: center; justify-content: center; padding: var(--space-md); color: var(--text-secondary); gap: var(--space-sm); font-style: italic; }
    .spinner { border: 3px solid rgba(0, 0, 0, 0.1); border-top: 3px solid var(--secondary); border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }

    .input-area {
        padding: var(--space-sm) var(--space-lg) var(--space-md);
        border-top: 1px solid var(--input-border);
        background-color: var(--bg-surface);
        flex-shrink: 0;
         display: flex;
         flex-direction: column;
         gap: var(--space-sm); /* Consistent gap */
    }

    /* --- Styles for Collapsible Section --- */
    .constitution-toggle-area {
         display: flex;
         justify-content: flex-end; /* Align toggle button to the right */
    }
    .toggle-button {
         background: none;
         border: 1px solid var(--input-border);
         color: var(--text-secondary);
         padding: var(--space-xs) var(--space-sm);
         border-radius: var(--radius-md);
         cursor: pointer;
         font-size: 0.8em;
         display: inline-flex; /* Use inline-flex */
         align-items: center;
         gap: var(--space-xs);
         transition: background-color 0.2s ease, border-color 0.2s ease;
    }
    .toggle-button:hover {
         background-color: var(--bg-elevated);
         border-color: var(--primary-light);
    }
    .toggle-icon {
         display: inline-block;
         transition: transform 0.2s ease-in-out;
         font-size: 0.9em; /* Slightly larger icon */
    }
    .toggle-icon.rotated {
         transform: rotate(180deg);
    }
    .selector-wrapper {
         /* Wrapper helps with transition */
         overflow: hidden;
         border: 1px solid var(--input-border); /* Optional border around selector */
         border-radius: var(--radius-md);
         margin-bottom: var(--space-xs); /* Space below selector */
    }

    /* --- Mobile adjustments --- */
     @media (max-width: 768px) { /* ... existing mobile styles ... */ }
</style>
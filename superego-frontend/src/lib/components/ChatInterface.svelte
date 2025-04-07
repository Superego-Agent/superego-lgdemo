<script lang="ts">
    // Updated imports
    import {
        messages,
        isLoading,
        globalError,
        activeThreadId,
        activeConversationId,
        // activeConstitutionIds, // No longer directly used for sending
        availableConstitutions, // Needed for titles
        constitutionAdherenceLevels // The new source of truth for active constitutions and levels
    } from '../stores';
    import { streamRun, fetchHistory } from '../api'; // Added fetchHistory
    import { createNewConversation } from '../conversationManager'; // Import conversation creation function
    import MessageCard from './MessageCard.svelte';
    import ChatInput from './ChatInput.svelte';
    import ConstitutionSelector from './ConstitutionSelector.svelte';
    import { afterUpdate, onMount, onDestroy } from 'svelte'; // Added onDestroy for potential cleanup
    import { slide, fade } from 'svelte/transition';
    import { nanoid } from 'nanoid';

    let chatContainer: HTMLElement;
    let isAtBottom = true;
    let isConstitutionSelectorVisible = false; // State for collapsible selector
    let initialLoadComplete = false; // Flag to prevent fetch on initial null threadId

    // --- Auto-scroll Logic ---
    function checkScroll() {
        if (chatContainer) {
            const threshold = 50; // Pixels from bottom
            isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < threshold;
        }
    }
    afterUpdate(() => {
        if (chatContainer && isAtBottom) {
            // Use requestAnimationFrame for smoother scroll after DOM updates
            requestAnimationFrame(() => {
                 chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
            });
        }
    });

    // --- Initialize constitution visibility & Load initial history ---
    onMount(() => {
        // Check initial state
        const initialThreadId = $activeThreadId;
        isConstitutionSelectorVisible = (initialThreadId === null);

        if (initialThreadId) {
            console.log(`ChatInterface onMount: Loading history for initial thread ${initialThreadId}`);
            fetchHistory(initialThreadId).catch(err => {
                console.error("Error loading initial history:", err);
                // Error handled by globalError store
            }).finally(() => {
                initialLoadComplete = true;
            });
        } else {
            console.log("ChatInterface onMount: No initial thread selected.");
            messages.set([]); // Ensure messages are clear for new chat
            initialLoadComplete = true;
        }
    });

    // --- Reactive History Loading ---
    $: if (initialLoadComplete && $activeThreadId) {
        // Only fetch if the thread ID changes *after* initial mount
        console.log(`ChatInterface reactive: Loading history for thread ${$activeThreadId}`);
        fetchHistory($activeThreadId).catch(err => {
            console.error(`Error loading history for thread ${$activeThreadId}:`, err);
            // Error handled by globalError store
        });
    } else if (initialLoadComplete && $activeThreadId === null) {
        // Clear messages if user selects "New Chat" after initial load
        console.log("ChatInterface reactive: New chat selected, clearing messages.");
        messages.set([]);
    }

    // --- Reactive Constitution Selector Visibility ---
    // Auto-expand on new chat (when activeThreadId becomes null)
    $: if ($activeThreadId === null && !isConstitutionSelectorVisible) {
         isConstitutionSelectorVisible = true;
    }
    // Auto-collapse if a thread is selected and it was previously visible
    $: if ($activeThreadId !== null && isConstitutionSelectorVisible) {
        // Optional: Auto-collapse when selecting an existing thread
        // isConstitutionSelectorVisible = false;
    }


    // --- Message Sending Logic ---
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        if (!userInput || $isLoading) {
            console.log("Send cancelled: input empty or already loading.");
            return;
        }

        let currentThreadId = $activeThreadId; // Capture current thread ID
        let currentConversationId = $activeConversationId; // Capture current conversation ID

        // --- Create new conversation if needed ---
        if (currentThreadId === null) {
            console.log("Creating new conversation locally...");
            const newConversation = createNewConversation(); // Create new conversation entry
            if (newConversation) {
                currentConversationId = newConversation.id; // Get the new client-side ID
                activeConversationId.set(currentConversationId); // Set it as active *before* sending
                // currentThreadId remains null, as the backend will assign it
                console.log(`New conversation created locally with ID: ${currentConversationId}. Active ID set.`);
            } else {
                console.error("Failed to create new conversation locally.");
                globalError.set("Failed to initialize new chat session.");
                return; // Stop if creation failed
            }
        }

        // Optimistically add user message
        const userMessage: HumanMessage = {
            id: nanoid(8),
            sender: 'human',
            content: userInput,
            timestamp: Date.now()
        };
        messages.update(msgs => [...msgs, userMessage]);

        // --- Format Adherence Levels ---
        let adherenceLevelsText = "";
        const levels = $constitutionAdherenceLevels;
        const activeIds = Object.keys(levels);

        if (activeIds.length > 0) {
            const constitutionsMap = $availableConstitutions.reduce((acc, c) => {
                acc[c.id] = c.title;
                return acc;
            }, {} as Record<string, string>);

            const levelLines = activeIds.map(id => {
                const title = constitutionsMap[id] || id; // Fallback to ID if title not found
                const level = levels[id];
                return `${title}: Level ${level}/5`;
            });
            adherenceLevelsText = "# User-Specified Adherence Levels\n" + levelLines.join('\n');
        }
        // --- End Format Adherence Levels ---

        // Use activeIds derived from adherence levels store
        console.log(`Sending message to thread ${currentThreadId === null ? 'NEW (Client ID: ' + currentConversationId + ')' : currentThreadId} with constitutions: ${activeIds.join(', ') || 'none'}`);
        console.log(`Adherence Levels Payload:\n${adherenceLevelsText || '(None)'}`);


        // Collapse selector after sending message in a new chat
        if (currentThreadId === null && isConstitutionSelectorVisible) {
            isConstitutionSelectorVisible = false;
        }

        try {
            // Call streamRun, passing null for threadId if it's a new chat
            // Pass activeIds derived from adherence levels, and the formatted text
            await streamRun(userInput, currentThreadId, activeIds, adherenceLevelsText);
            // Stream 'end' event in api.ts now handles updating conversation metadata using the activeConversationId set above
        } catch (error) {
            console.error("Error during streamRun:", error);
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
             <div transition:fade={{ duration: 300 }}>
                  <MessageCard {message} />
             </div>
        {:else}
            {#if !initialLoadComplete}
                 <div class="loading-indicator">
                      <div class="spinner"></div>
                      <span>Loading History...</span>
                  </div>
            {:else}
                 <div class="empty-chat" transition:fade={{ duration: 500 }}>
                      <div class="empty-chat-icon">💬</div>
                      <p>Select constitution(s) and send a message</p>
                  </div>
            {/if}
        {/each}
        

        {#if $isLoading}
            <div class="loading-indicator">
                  <div class="spinner"></div>
                  <span>Thinking...</span>
              </div>
        {/if}
    </div>

    <div class="input-area">
        <ConstitutionSelector />
         {/* @ts-ignore */ null}
        <ChatInput on:send={handleSend} disabled='{$isLoading}' />
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
        background-color: var(--bg-primary); /* Changed background to primary */
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
          /* border: 1px solid var(--input-border); */ /* REMOVED BORDER */
          border-radius: var(--radius-md);
          /* margin-bottom: var(--space-xs); */ /* Removed margin, rely on gap */
     }

    /* --- Mobile adjustments --- */
     @media (max-width: 768px) { /* ... existing mobile styles ... */ }
</style>

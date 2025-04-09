<script lang="ts">
    import { globalError, activeSessionId, uiSessions, knownThreadIds } from '../stores';
    import { streamRun, getLatestHistory } from '../api';
    import { addThreadToSession } from '../sessionManager'; // Import session management function
    import { get } from 'svelte/store';
    import { afterUpdate, tick } from 'svelte';
    import { slide, fade } from 'svelte/transition';
    import MessageCard from './MessageCard.svelte';
    import ChatInput from './ChatInput.svelte';
    import ConstitutionSelector from './ConstitutionSelector.svelte'; // Keep for layout, config integration pending
    import ErrorIcon from '~icons/fluent/warning-24-regular';
    import ChatIcon from '~icons/fluent/chat-24-regular';
    import InfoIcon from '~icons/fluent/info-24-regular';
    // Types from global.d.ts (HistoryEntry, MessageType, RunConfig, etc.) are globally available

    let chatContainer: HTMLElement;
    let isAtBottom = true;
    let isLoadingHistory = false;
    let isStreaming = false;
    let historyError: string | null = null;
    // Store the latest history entry for the *single* active thread in the current session
    // TODO: Adapt for compare mode (multiple threads/entries) later
    let activeHistoryEntry: HistoryEntry | null = null;

    // --- Auto-scroll Logic ---
    function checkScroll() {
        if (chatContainer) {
            const threshold = 50; // Pixels from bottom
            isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < threshold;
        }
    }
    afterUpdate(async () => {
        if (chatContainer && isAtBottom) {
            await tick(); // Wait for DOM updates
             requestAnimationFrame(() => {
                 chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'auto' }); // Use auto for instant scroll after stream/load
             });
        }
    });

    // --- Reactive State Derivations ---
    $: currentSessionId = $activeSessionId;
    $: currentSessionState = currentSessionId ? $uiSessions[currentSessionId] : null;
    // For now, assume single thread per session for display
    $: activeThreadId = currentSessionState?.threadIds?.[0] ?? null;

    $: displayedMessages = activeHistoryEntry?.values?.messages ?? []; // Type is inferred
    $: currentRunConfig = activeHistoryEntry?.runConfig ?? null; // Type is inferred
    $: isProcessing = isLoadingHistory || isStreaming;

    // --- Fetch History on Session Change ---
    $: if (currentSessionId && activeThreadId) {
        loadHistory(activeThreadId);
    } else if (currentSessionId && !activeThreadId) {
        // Session exists but has no threads yet (new session)
        activeHistoryEntry = null;
        historyError = null;
        isLoadingHistory = false;
    } else {
         // No active session selected
         activeHistoryEntry = null;
         historyError = null;
         isLoadingHistory = false;
    }

    async function loadHistory(threadId: string) {
        if (!threadId) return;
        // console.log(`[ChatInterface] Loading history for thread: ${threadId}`);
        isLoadingHistory = true;
        historyError = null;
        activeHistoryEntry = null; // Clear previous entry
        isAtBottom = true; // Ensure scroll to bottom after load
        try {
            const history = await getLatestHistory(threadId);
            activeHistoryEntry = history;
            // console.log('[ChatInterface] History loaded:', history);
        } catch (error: unknown) {
            console.error(`[ChatInterface] Error loading history for thread ${threadId}:`, error);
            const message = error instanceof Error ? error.message : String(error);
            historyError = `Failed to load conversation history: ${message}`;
            globalError.set(historyError); // Also show in global banner
        } finally {
            isLoadingHistory = false;
        }
    }

    // --- Message Sending Logic ---
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        if (!userInput || isProcessing || !currentSessionId) {
            console.warn('[ChatInterface] Send prevented:', { userInput, isProcessing, currentSessionId });
            return;
        }

        const sessionState = $uiSessions[currentSessionId];
        if (!sessionState) {
             globalError.set("Cannot send message: Active session not found.");
             return;
        }

        // Determine target thread ID (null if session has no threads yet)
        const targetThreadId = sessionState.threadIds?.[0] ?? null;

        // --- !!! PLACEHOLDER FOR RunConfig !!! ---
        // TODO: Get the actual RunConfig from the refactored ConstitutionSelector component.
        // This requires ConstitutionSelector to be updated to manage its state and expose
        // the selected configuredModules.
        const placeholderRunConfig: RunConfig = {
             configuredModules: [
                 // Example placeholder - replace with actual data from ConstitutionSelector
                 // { id: 'default-safety', title: 'Default Safety', adherence_level: 3 }
             ]
         };
        // --- End Placeholder ---

        console.log(`[ChatInterface] Sending message to thread: ${targetThreadId ?? '(new thread)'}`);
        isStreaming = true;
        historyError = null; // Clear previous errors
        globalError.set(null); // Clear global error
        isAtBottom = true; // Ensure scroll to bottom during streaming

        try {
            await streamRun(userInput, placeholderRunConfig, {
                thread_id: targetThreadId, // Pass explicitly for clarity, api.ts uses this
                onThreadInfo: (data) => {
                    const newThreadId = data.thread_id;
                    console.log(`[ChatInterface] Received thread_info: ${newThreadId}`);
                    if (currentSessionId && !targetThreadId) {
                        // Add to known threads if not already there
                        if (!get(knownThreadIds).includes(newThreadId)) {
                            knownThreadIds.update(ids => [...ids, newThreadId]);
                        }
                        // Add thread to the current UI session
                        addThreadToSession(currentSessionId, newThreadId);
                        console.log(`[ChatInterface] Added new thread ${newThreadId} to session ${currentSessionId}`);
                    } else if (targetThreadId && targetThreadId !== newThreadId) {
                         console.warn(`[ChatInterface] Received thread_info for unexpected thread ID: ${newThreadId} (expected ${targetThreadId})`);
                    }
                },
                onChunk: (/* chunk */) => {
                    // For now, we don't do optimistic updates from raw chunks.
                    // We rely on the final state from onEnd -> loadHistory.
                    // console.log('[ChatInterface] Received chunk:', chunk);
                    // Potentially update a temporary streaming message here in the future.
                },
                onEnd: (data) => {
                    console.log(`[ChatInterface] Stream ended for thread: ${data.thread_id}, final checkpoint: ${data.checkpoint_id}`);
                    isStreaming = false;
                    // Reload history to get the definitive final state
                    loadHistory(data.thread_id);
                },
                onError: (errorData) => {
                    console.error('[ChatInterface] SSE Error:', errorData);
                    isStreaming = false;
                    const message = errorData.message || 'Unknown streaming error';
                    historyError = `Streaming error: ${message}`;
                    globalError.set(historyError);
                }
            });
        } catch (error: unknown) {
            console.error("[ChatInterface] Error calling streamRun:", error);
            isStreaming = false;
            const message = error instanceof Error ? error.message : String(error);
            historyError = `Failed to send message: ${message}`;
            globalError.set(historyError);
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
        {#if isLoadingHistory}
            <div class="loading-indicator">
                <div class="spinner"></div>
                <span>Loading History...</span>
            </div>
        {:else if historyError}
            <div class="empty-chat error-message" transition:fade={{ duration: 500 }}>
                <div class="empty-chat-icon"><ErrorIcon /></div>
                <p>Error loading conversation:</p>
                <p><small>{historyError}</small></p>
            </div>
        {:else if !currentSessionId}
            <div class="empty-chat" transition:fade={{ duration: 500 }}>
                <div class="empty-chat-icon"><ChatIcon /></div>
                <p>Select or start a new session</p>
                <p><small>(Use the sidebar to manage sessions)</small></p>
            </div>
        {:else if displayedMessages.length === 0 && !isStreaming}
             <div class="empty-chat" transition:fade={{ duration: 500 }}>
                 <div class="empty-chat-icon"><ChatIcon /></div>
                 <p>Send a message to start the run.</p>
                 {#if currentSessionState?.name}
                     <p><small>Session: {currentSessionState.name}</small></p>
                 {/if}
             </div>
        {:else}
            {#each displayedMessages as message (message.id || message.content)} <!-- Use content as fallback key -->
                <div transition:fade={{ duration: 300 }}>
                    <MessageCard {message} />
                </div>
            {/each}
        {/if}

        {#if isStreaming}
            <!-- Optional: Add a more specific streaming indicator if needed -->
            <!-- <div class="loading-indicator"> -->
            <!--     <div class="spinner"></div> -->
            <!--     <span>Agent is thinking...</span> -->
            <!-- </div> -->
        {/if}

        {#if currentRunConfig && currentRunConfig.configuredModules.length > 0 && !isLoadingHistory && !historyError}
             <div class="run-config-info" title="Configuration used for the last displayed message(s)">
                 <span class="info-icon"><InfoIcon /></span>
                 <span>Active Constitution(s):</span>
                 <ul>
                     {#each currentRunConfig.configuredModules as mod}
                         <li>{mod.title} (Level {mod.adherence_level})</li>
                     {/each}
                 </ul>
             </div>
         {/if}
    </div>

    <div class="input-area">
         <!-- ConstitutionSelector is kept for layout. Integration is pending its refactor. -->
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
        padding: var(--space-sm) var(--space-md); // Reduced padding
        border-bottom: 1px solid var(--error);
        text-align: center;
        font-size: 0.85em; // Smaller font
        box-shadow: var(--shadow-sm); // Lighter shadow
        flex-shrink: 0;
        z-index: 10; // Ensure it's above messages
    }
    .error-content {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--space-xs); // Reduced gap
    }
    .error-icon {
        font-size: 1.1em; // Slightly smaller icon
        flex-shrink: 0;
    }
    .messages-container {
        flex-grow: 1;
        overflow-y: auto;
        padding: var(--space-md) var(--space-lg); // Adjusted padding
        display: flex;
        flex-direction: column;
        gap: var(--space-md);
        -webkit-overflow-scrolling: touch;
        @include custom-scrollbar();
        position: relative; // Needed for absolute positioning of run-config-info
    }
    .empty-chat {
        text-align: center;
        color: var(--text-secondary);
        margin: auto 0; /* Center vertically */
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
        margin: auto 0; // Center vertically if it's the only thing
    }
    .spinner {
        @include loading-spinner(1.2em, 2px, var(--text-secondary)); // Slightly smaller spinner
    }

    .run-config-info {
        font-size: 0.75em;
        color: var(--text-tertiary);
        background-color: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-sm);
        padding: var(--space-xs) var(--space-sm);
        margin: var(--space-sm) auto 0; // Center horizontally, add top margin
        display: inline-flex; // Fit content width
        align-items: center;
        gap: var(--space-xs);
        max-width: 90%; // Prevent excessive width
        position: sticky; // Keep it visible at the bottom
        bottom: var(--space-xs); // Small offset from the bottom edge
        left: 50%;
        transform: translateX(-50%);
        z-index: 5; // Above messages but below error banner

        .info-icon {
            font-size: 1.2em;
            flex-shrink: 0;
        }

        ul {
            list-style: none;
            padding: 0;
            margin: 0;
            display: inline; // Keep items inline if possible
        }
        li {
            display: inline;
            margin-left: var(--space-xs);
            &:not(:last-child)::after {
                content: ', '; // Separate items with commas
            }
        }
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

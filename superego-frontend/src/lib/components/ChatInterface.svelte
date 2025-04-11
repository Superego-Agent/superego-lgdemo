<script lang="ts">
    import { globalError, setGlobalError, persistedActiveSessionId, persistedUiSessions } from '../stores.svelte';
    import { sendUserMessage } from '../services/chatService';
    import ChatInput from './ChatInput.svelte';
    import RunConfigurationPanel from './RunConfigurationPanel.svelte';
    import ChatView from './ChatView.svelte';
    import Paginator from './Paginator.svelte';
    import IconChat from '~icons/fluent/chat-24-regular';

    // --- Constants ---
    const MIN_CHAT_VIEW_WIDTH = 400;

    // --- Component State ---
    let containerWidth: number = $state(0);

    // --- Reactive State Derivations ---
    let currentSessionId = $derived(persistedActiveSessionId.state);
    let currentSessionState = $derived(currentSessionId ? persistedUiSessions.state[currentSessionId] : null);
    let activeThreadIds = $derived(currentSessionState?.threads ? Object.keys(currentSessionState.threads) : []);


    // --- Event Handlers ---
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        if (!userInput || !currentSessionId) {
            console.warn('[ChatInterface] Send prevented: No input or active session.', { userInput, currentSessionId });
            return;
        }

        const sessionState = persistedUiSessions.state[currentSessionId];
        if (!sessionState) {
             // Setting globalError here might be redundant if sendUserMessage handles it,
             // but it provides immediate feedback if the session is missing.
             setGlobalError("Cannot send message: Active session not found.");
             console.error('[ChatInterface] Send prevented: Session state not found for ID:', currentSessionId);
             return;
        }

        console.log(`[ChatInterface] Calling sendUserMessage for session: ${currentSessionId}`);
        // Call the service function, which handles config and API call
        await sendUserMessage(userInput);
    }

</script>

<div class="chat-interface">
    <!-- === Global Error Banner === -->
    {#if globalError}
        <div class="error-banner" >
             <div class="error-content">
                 <span>Error: {globalError}</span>
             </div>
         </div>
    {/if}

    <!-- === Main Chat Display Area === -->
    <div class="messages-container" bind:clientWidth={containerWidth}>
        {#if activeThreadIds.length > 0}
             <Paginator items={activeThreadIds} {containerWidth} minItemWidth={MIN_CHAT_VIEW_WIDTH} >
                 {#snippet children({ paginatedItems })}
                                <div class="page-content">
                         {#each paginatedItems as threadId (threadId)}
                             <div class="thread-wrapper">
                                 <ChatView {threadId} />
                             </div>
                         {/each}
                     </div>
                                             {/snippet}
                        </Paginator>
        {:else if currentSessionId}
            <div class="empty-chat">
                <IconChat />
                <p>Configure your superego's available constitution module(s), then enter a message to begin.</p>
             </div>
        {:else}
             <div class="empty-chat">
                 <p>Select or start a new session.</p>
             </div>
        {/if}
    </div>

    <!-- === Input Area (Config Panel + Chat Input) === -->
    <div class="input-area">
        <RunConfigurationPanel />
        <ChatInput on:send={handleSend} disabled={!currentSessionId} />
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
 .messages-container {
     flex-grow: 1;
     overflow: hidden; /* Hide main scrollbar, page content scrolls if needed */
     padding: 0; /* Remove padding, apply to page-content if needed */
     display: flex;
     flex-direction: column; /* Stack page content and pagination */
     gap: var(--space-sm); /* Space between page content and pagination */
     -webkit-overflow-scrolling: touch;
 }
 .page-content {
     flex-grow: 1;
     display: flex;
     flex-direction: row; /* Side-by-side layout */
     gap: var(--space-sm);
     padding: var(--space-md); /* Add padding here */
     overflow-x: hidden; /* Prevent horizontal scrollbar */
     overflow-y: hidden; /* ChatView handles its own scroll */
 }

 .thread-wrapper {
     flex: 1; /* Share space equally */
     display: flex; /* Ensure ChatView fills wrapper */
     min-width: 0; /* Prevent flex overflow issues */
     border: 1px solid var(--border-color-light, #eee); /* Optional border */
     border-radius: var(--radius-md);
     overflow: hidden; /* Clip content */
 }

 .empty-chat {
     text-align: center;
     color: var(--text-secondary);
     margin: auto; /* Center vertically and horizontally */
     padding: var(--space-xl);
     font-style: italic;
     display: flex;
     flex-direction: column;
     align-items: center;
     justify-content: center;
     gap: var(--space-sm);
 }



 .input-area {
     padding: var(--space-md);
     background-color: var(--bg-primary);
     flex-shrink: 0;
     display: flex;
     flex-direction: column;
     gap: var(--space-sm);
  }
</style>
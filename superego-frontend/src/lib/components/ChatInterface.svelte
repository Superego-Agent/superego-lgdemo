<script lang="ts">
    import { globalError, activeSessionId, uiSessions } from '../stores';
    import { sendUserMessage } from '../services/chatService';
    import ChatInput from './ChatInput.svelte';
    import RunConfigurationPanel from './RunConfigurationPanel.svelte';
    import ChatView from './ChatView.svelte'; 
    import IconChat from '~icons/fluent/chat-24-regular';

    import ChevronLeftIcon from '~icons/fluent/chevron-left-24-regular';
    import ChevronRightIcon from '~icons/fluent/chevron-right-24-regular';

    // --- Pagination State ---
    const MIN_CHAT_VIEW_WIDTH = 400; // Minimum width for each ChatView in pixels
    let containerWidth: number = 0; // Bound to messages-container width
    let currentPage = 0;
    let itemsPerPage = 1;
    let totalPages = 1;
    let paginatedThreadIds: string[] = [];

    // --- Reactive State Derivations ---
    $: currentSessionId = $activeSessionId;
    $: currentSessionState = currentSessionId ? $uiSessions[currentSessionId] : null;
    $: activeThreadIds = currentSessionState?.threads ? Object.keys(currentSessionState.threads) : [];

    // --- Reactive Pagination Calculations ---
    $: {
        itemsPerPage = Math.max(1, Math.floor(containerWidth / MIN_CHAT_VIEW_WIDTH));
        totalPages = Math.ceil(activeThreadIds.length / itemsPerPage);
        // Clamp currentPage to valid range if totalPages changes
        currentPage = Math.max(0, Math.min(currentPage, totalPages - 1));

        const startIndex = currentPage * itemsPerPage;
        const endIndex = startIndex + itemsPerPage;
        paginatedThreadIds = activeThreadIds.slice(startIndex, endIndex);
    }

    // --- Pagination Functions ---
    function goToPage(pageIndex: number) {
        currentPage = Math.max(0, Math.min(pageIndex, totalPages - 1));
    }
    function nextPage() {
        if (currentPage < totalPages - 1) {
            currentPage++;
        }
    }
    function prevPage() {
        if (currentPage > 0) {
            currentPage--;
        }
    }

    // --- Event Handlers ---
    async function handleSend(event: CustomEvent<{ text: string }>) {
        const userInput = event.detail.text.trim();
        if (!userInput || !currentSessionId) {
            console.warn('[ChatInterface] Send prevented: No input or active session.', { userInput, currentSessionId });
            return;
        }

        const sessionState = $uiSessions[currentSessionId];
        if (!sessionState) {
             // Setting globalError here might be redundant if sendUserMessage handles it,
             // but it provides immediate feedback if the session is missing.
             globalError.set("Cannot send message: Active session not found.");
             console.error('[ChatInterface] Send prevented: Session state not found for ID:', currentSessionId);
             return;
        }

        console.log(`[ChatInterface] Calling sendUserMessage for session: ${currentSessionId}`);
        // Call the service function, which handles config and API call
        await sendUserMessage(userInput);
    }

</script>

<div class="chat-interface">
    {#if $globalError}
        <div class="error-banner" >
             <div class="error-content">
                 <span>Error: {$globalError}</span>
             </div>
         </div>
    {/if}

    <div class="messages-container" bind:clientWidth={containerWidth}>
        {#if activeThreadIds.length > 0}
            <!-- Page Content: Displays ChatViews for the current page -->
            <div class="page-content">
                {#each paginatedThreadIds as threadId (threadId)}
                    <div class="thread-wrapper">
                        <ChatView {threadId} />
                    </div>
                {/each}
            </div>
            <!-- Pagination Controls -->
            {#if totalPages > 1}
                <div class="pagination-controls">
                    <button class="pagination-button" on:click={prevPage} disabled={currentPage === 0} aria-label="Previous Page">
                        <ChevronLeftIcon />
                    </button>
                    <div class="pagination-dots">
                        {#each { length: totalPages } as _, i}
                            <button
                                class="dot"
                                class:active={i === currentPage}
                                on:click={() => goToPage(i)}
                                aria-label="Go to page {i + 1}"
                                aria-current={i === currentPage ? 'page' : undefined}
                            ></button>
                        {/each}
                    </div>
                    <button class="pagination-button" on:click={nextPage} disabled={currentPage === totalPages - 1} aria-label="Next Page">
                        <ChevronRightIcon />
                    </button>
                </div>
            {/if}
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

 .pagination-controls {
     display: flex;
     justify-content: center;
     align-items: center;
     padding: var(--space-xs) 0 var(--space-sm);
     flex-shrink: 0;
     gap: var(--space-md);
 }

 .pagination-button {
     background: none;
     border: none;
     color: var(--text-secondary);
     cursor: pointer;
     padding: var(--space-xs);
     border-radius: var(--radius-sm);
     display: flex;
     align-items: center;
     justify-content: center;
     font-size: 1.2em;

     &:hover:not(:disabled) {
         background-color: var(--bg-hover);
         color: var(--text-primary);
     }

     &:disabled {
         color: var(--text-disabled);
         cursor: not-allowed;
     }
 }

 .pagination-dots {
     display: flex;
     gap: var(--space-xs);
 }

 .dot {
     width: 10px;
     height: 10px;
     border-radius: 50%;
     background-color: var(--secondary);
     border: none;
     padding: 0;
     cursor: pointer;
     transition: background-color 0.2s ease;

     &:hover {
         background-color: var(--text-secondary);
     }

     &.active {
         background-color: var(--primary);
     }
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
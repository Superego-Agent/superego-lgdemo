<script lang="ts">
  import { activeStore } from "$lib/state/active.svelte";
  import IconChat from "~icons/fluent/chat-24-regular";
  import { sendUserMessage } from "../services/chat.svelte";
  import { sessionStore } from "../state/session.svelte";
  import { threadStore } from "../state/threads.svelte";
  import { getLatestHistory } from "../api/rest.svelte";
  import ChatInput from "./ChatInput.svelte";
  import ChatView from "./ChatView.svelte";
  import Paginator from "./Paginator.svelte";
  import RunConfigurationPanel from "./RunConfigurationPanel.svelte";

  // --- Constants ---
  const MIN_CHAT_VIEW_WIDTH = 400;

  // --- Component State ---
  let containerWidth: number = $state(0);

  // --- Reactive State Derivations ---
  // Access persisted state directly via the store instance properties
  let currentSessionId = $derived(sessionStore.activeSessionId);
  let currentSessionState = $derived(
    currentSessionId ? sessionStore.uiSessions[currentSessionId] : null
  );
  let activeThreadIds = $derived(
    currentSessionState?.threads ? Object.keys(currentSessionState.threads) : []
  );


  // --- Effect for Lazy Loading History ---
  $effect(() => {
    // This effect runs when the active session changes, giving us the list of relevant thread IDs
    const threadsForCurrentSession = activeThreadIds; // Use the derived list of thread IDs for the session
    
    if (!threadsForCurrentSession || threadsForCurrentSession.length === 0) {
        return; // No threads in this session
    }

    // Iterate through each thread associated with the current session
    for (const threadId of threadsForCurrentSession) {
        const threadCache = threadStore.threadCacheStore;
        const currentEntry = threadCache[threadId];
        // Check if THIS threadId is known
        const isKnown = sessionStore.knownThreadIds.includes(threadId);

        // Conditions to fetch for THIS threadId:
        // 1. Thread is known to backend (dispatched)
        // 2. History is not already present in cache for this thread
        // 3. Not currently loading for this thread
        if (isKnown && (!currentEntry || (!currentEntry.history && !currentEntry.isLoading))) {
            // Wrap async logic in an IIAFE for each thread fetch
            (async () => {
                try {
                    // Set loading state for this thread
                    threadStore.updateEntry(threadId, { isLoading: true, error: null });

                    // Fetch history for this thread
                    const historyResult = await getLatestHistory(threadId);

                    // Update store on success for this thread
                    threadStore.updateEntry(threadId, { history: historyResult, isLoading: false });
                    
                } catch (error: any) {
                    // Handle errors, including AbortError
                    if (error.name === 'AbortError') {
                        console.warn(`[ChatInterface Effect] History fetch aborted for thread: ${threadId}`);
                        // Reset loading state on abort for this thread
                        threadStore.updateEntry(threadId, { isLoading: false });
                    } else {
                        console.error(`[ChatInterface Effect] Error loading history for thread ${threadId}:`, error);
                        const errorMessage = error instanceof Error ? error.message : String(error);
                         // Update store on error for this thread
                        threadStore.updateEntry(threadId, { error: `Failed to load history: ${errorMessage}`, isLoading: false });
                    }
                }
            })(); // Immediately invoke the async function
        }
    }
  });

  // --- Event Handlers ---
  async function handleSend(detail: { text: string }) {
    const userInput = detail.text.trim();
    if (!userInput || !currentSessionId) {
      console.warn(
        "[ChatInterface] Send prevented: No input or active session.",
        { userInput, currentSessionId }
      );
      return;
    }

    // Use the derived value here too
    // Access persisted state directly
    const currentSessionData = currentSessionId
      ? sessionStore.uiSessions[currentSessionId]
      : null;
    if (!currentSessionData) {
      // Setting globalError here might be redundant if sendUserMessage handles it,
      // but it provides immediate feedback if the session is missing.
      activeStore.setGlobalError(
        "Cannot send message: Active session not found."
      );
      console.error(
        "[ChatInterface] Send prevented: Session state not found for ID:",
        currentSessionId
      );
      return;
    }

    console.log(
      `[ChatInterface] Calling sendUserMessage for session: ${currentSessionId}`
    );
    // Call the service function, which handles config and API call
    await sendUserMessage(userInput);
  }
</script>

<div class="chat-interface">
  <!-- === Global Error Banner === -->
  {#if activeStore.globalError}
    <div class="error-banner">
      <div class="error-content">
        <span>Error: {activeStore.globalError}</span>
      </div>
    </div>
  {/if}

  <!-- === Main Chat Display Area === -->
  <div class="messages-container" bind:clientWidth={containerWidth}>
    {#if activeThreadIds.length > 0}
      <Paginator
        items={activeThreadIds}
        {containerWidth}
        minItemWidth={MIN_CHAT_VIEW_WIDTH}
      >
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
        <p>
          Configure your superego's available constitution module(s), then enter
          a message to begin.
        </p>
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
    <ChatInput onSend={handleSend} disabled={!currentSessionId} />
  </div>
</div>

<style lang="scss">
  @use "../styles/mixins" as *;

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

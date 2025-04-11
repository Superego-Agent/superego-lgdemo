<script lang="ts">
  import { preventDefault } from 'svelte/legacy';

  import { tick } from "svelte";
  import { sessionState } from "../state/session.svelte";

  import IconEdit from "~icons/fluent/edit-24-regular";
  import IconDelete from "~icons/fluent/delete-24-regular";
  import IconAdd from "~icons/fluent/add-24-regular";

  // --- Component State ---
  let editingSessionId: string | null = $state(null);
  let editingName: string = $state("");
  let originalEditingName: string = "";
  let renameInput: HTMLInputElement | null = $state(null);

  // --- Reactive Derivations ---
  let sortedSessions = $derived(Object.values(sessionState.uiSessions).sort(
    (a: UISessionState, b: UISessionState) =>
      new Date(b.lastUpdatedAt).getTime() - new Date(a.lastUpdatedAt).getTime()
  ));

  // --- Functions ---
  function handleNewChat() {
    sessionState.createNewSession();
  }

  function selectConversation(sessionId: string) {
    if (sessionId === sessionState.activeSessionId) return;
    editingSessionId = null;
    sessionState.activeSessionId = sessionId;
  }

  function startRename(event: MouseEvent, session: UISessionState) {
    event.stopPropagation();
    editingSessionId = session.sessionId;
    editingName = session.name;
    originalEditingName = session.name;
    tick().then(() => {
      renameInput?.focus();
      renameInput?.select();
    });
  }

  function handleRename() {
    if (editingSessionId === null) return;

    const sessionIdToRename = editingSessionId;
    const newName = editingName.trim();
    const originalName = originalEditingName;

    editingSessionId = null;

    if (!newName || newName === originalName) {
      return;
    }

    sessionState.renameSession(sessionIdToRename, newName);
  }

  function handleRenameKeyDown(event: KeyboardEvent) {
    if (event.key === "Enter") {
      event.preventDefault();
      handleRename();
    } else if (event.key === "Escape") {
      editingSessionId = null;
    }
  }

  async function handleDelete(event: MouseEvent, sessionId: string) {
    event.stopPropagation();

    // Use $uiSessions store directly
    const sessionToDelete = sessionState.uiSessions[sessionId];
    if (!sessionToDelete) return;

    if (
      !confirm(
        `Are you sure you want to delete session "${sessionToDelete.name}"?`
      )
    ) {
      return;
    }

    // Call imported function to delete frontend session state
    // Direct mutation for now, assuming SessionStateStore handles persistence via $effect
    // and sessionManager.deleteSession will be updated/removed later.
    sessionState.deleteSession(sessionId);
  }
</script>

<div class="sidebar">

  <div class="sidebar-section threads-section">
    <!-- === Session List === -->
    <ul class="thread-list">
      <!-- Iterate over sortedSessions derived from $uiSessions -->
      <!-- New Session Button as first list item -->
      <li class="new-session-list-item">
        <button
          class="new-session-button session-item-base"
          onclick={handleNewChat}
          title="New Session"
        >
          <IconAdd />
          <span>Add Session</span>
        </button>
      </li>
      {#each sortedSessions as session (session.sessionId)}
        <!-- Use $activeSessionId store directly -->
        <li
          class:active={session.sessionId === sessionState.activeSessionId}
          class:editing={editingSessionId === session.sessionId}
        >
          {#if editingSessionId === session.sessionId}
            <form class="rename-form" onsubmit={preventDefault(handleRename)}>
              <input
                type="text"
                bind:this={renameInput}
                bind:value={editingName}
                onblur={handleRename}
                onkeydown={handleRenameKeyDown}
                disabled={false}
                class="rename-input"
              />
            </form>
          {:else}
            <div
              class="thread-item-container session-item-base"
              onclick={() => selectConversation(session.sessionId)}
              role="button"
              tabindex="0"
              onkeydown={(e) => {
                if (e.key === "Enter" || e.key === " ")
                  selectConversation(session.sessionId);
              }}
            >
              <span class="thread-name">{session.name}</span>
              <div class="thread-actions">
                <button
                  class="icon-button"
                  title="Rename Session"
                  onclick={(e) => startRename(e, session)}
                  disabled={false}
                >
                  <IconEdit />
                </button>
                <button
                  class="icon-button delete-button"
                  title="Delete Session"
                  onclick={(e) => handleDelete(e, session.sessionId)}
                  disabled={false}
                >
                  <IconDelete />
                </button>
              </div>
            </div>
          {/if}
        </li>
      {:else}
        <li class="empty-list">No conversations yet.</li>
        <!-- === Empty List Message === -->
      {/each}
    </ul>
  </div>
</div>

<style lang="scss">
  @use "../styles/mixins" as *;

  .sidebar {
    width: 320px;
    min-width: 270px;
    background-color: var(--bg-sidebar);
    padding: var(--space-md);
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--input-border);
    height: 100%;
    overflow-y: auto;
    flex-shrink: 0;
    box-shadow: var(--shadow-lg);
    color: var(--text-primary);
    gap: var(--space-lg);
    font-size: 14pt;
    @include custom-scrollbar(
      $track-bg: var(--bg-sidebar),
      $thumb-bg: var(--primary-light),
      $width: 6px
    ); // Use mixin
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
    @include custom-scrollbar(
      $track-bg: transparent,
      $thumb-bg: var(--primary-light),
      $width: 4px
    ); // Use mixin
    display: block;

    li {
      /* Base styles for all list items */
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

  /* Base styles for all session items (existing and new button) */
  .session-item-base {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 12px 16px;
    border-radius: var(--radius-md);
    margin: 2px 0; /* Matches original .thread-item-container margin */
    transition:
      background-color 0.2s ease,
      color 0.2s ease,
      border-color 0.2s ease; /* Added color/border */
    cursor: pointer;
    overflow: hidden; /* Added from .thread-item-container */
    min-height: 48px; /* Ensure consistent minimum height */
    font-size: 12pt;
  }

  /* Specific styles for the new session button */
  .new-session-button {
    justify-content: flex-start; /* Align icon and text to start */
    gap: var(--space-sm); /* Add gap between icon and text */
    border: 2px dashed var(--input-border);
    background-color: var(
      --bg-elevated
    ); /* Use surface for better initial contrast */
    color: var(--primary);
    /* margin: 0; */ /* Inherits margin from .session-item-base */

    &:hover {
      background-color: var(--bg-surface); /* Use elevated for hover */
      border-color: var(--primary-light);
      color: var(--primary-); /* Keep icon color change on hover */
    }
  }

  /* Specific styles for existing session items */
  .thread-item-container {
    flex-grow: 1; /* Keep specific flex grow */
    justify-content: space-between;

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

    /* Ensure text size matches session names */
    .new-session-button span {
      font-size: 0.9em; /* Explicitly set font size for text */
      line-height: normal; /* Reset line-height if needed */
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
    transition:
      opacity 0.2s ease,
      background-color 0.2s ease,
      color 0.2s ease;
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

  @media (max-width: 768px) { }
</style>

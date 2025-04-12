<script lang="ts">
  import {
    fetchAvailableConstitutions,
    fetchConstitutionContent,
  } from "$lib/api/rest.svelte";
  import { activeStore } from "$lib/state/active.svelte";
  import { localConstitutionsStore } from "$lib/state/constitutions.svelte";
  import { sessionStore } from "$lib/state/session.svelte";

  import IconAdd from "~icons/fluent/add-24-regular";
  import IconChevronDown from "~icons/fluent/chevron-down-24-regular";
  import IconChevronUp from "~icons/fluent/chevron-up-24-regular";
  import IconInfo from "~icons/fluent/info-24-regular";
  
  import AddConstitutionModal from "./AddConstitutionModal.svelte";
  import ConstitutionInfoModal from "./ConstitutionInfoModal.svelte";
  import RunConfigManager from "./RunConfigManager.svelte";

  let isExpanded = $state(true);
  let showInfoModal = $state(false);
  let modalIsLoading = $state(false);
  let modalError: string | null = $state(null);
  let modalTitle: string = $state("");
  let modalDescription: string | undefined = $state(undefined);
  let modalContent: string | undefined = $state(undefined);
  let showAddModal = $state(false);

  // --- State for Global Constitutions (fetched locally) ---
  let globalConstitutionsList = $state<ConstitutionItem[]>([]);
  let isLoadingGlobal = $state(true);
  let globalErrorMsg = $state<string | null>(null);

  // --- Effect to fetch global constitutions ---
  $effect(() => {
    const controller = new AbortController();
    isLoadingGlobal = true;
    globalErrorMsg = null;
    globalConstitutionsList = []; // Clear previous list on fetch

    fetchAvailableConstitutions(controller.signal)
      .then((data) => {
        globalConstitutionsList = data;
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          console.error("Failed to fetch global constitutions:", err);
          globalErrorMsg =
            err.message || "Failed to load global constitutions.";
        }
      })
      .finally(() => {
        isLoadingGlobal = false;
      });

    return () => {
      controller.abort();
    };
  });

  async function showInfo(item: ConstitutionItem | LocalConstitution) {
    modalTitle = item.title;
    // Determine if it's global (has description) or local (has text)
    const isGlobal = "description" in item;

    modalDescription = isGlobal
      ? item.description
      : `Local constitution`;
    modalContent = undefined;
    modalError = null;
    modalIsLoading = true;
    showInfoModal = true;

    if (!isGlobal) {
      modalContent = (item as LocalConstitution).text;
      modalIsLoading = false;
    } else {
      // For global, fetch content
      try {
        modalContent = await fetchConstitutionContent(item.id);
      } catch (err: any) {
        console.error("Failed to fetch constitution content:", err);
        modalError = err.message || "Unknown error fetching content.";
      } finally {
        modalIsLoading = false;
      }
    }
  }

  function toggleExpand() {
    isExpanded = !isExpanded;
  }

  // --- Helper Functions for Direct Store Interaction ---

  function getActiveConfig(): ThreadConfigState | null {
    const currentSessionId = sessionStore.activeSessionId;
    if (!currentSessionId) return null;
    const currentSession = sessionStore.uiSessions[currentSessionId];
    const activeId = activeStore.activeConfigEditorId; // Use activeStore
    if (!activeId || !currentSession?.threads) return null;
    return currentSession.threads[activeId] ?? null;
  }

  function getModule(itemId: string): ConfiguredConstitutionModule | null {
    const activeConfig = getActiveConfig();
    return (
      activeConfig?.runConfig?.configuredModules?.find(
        (m) => m.id === itemId
      ) ?? null
    );
  }

  // Generic helper to update the configuredModules array in the store
  function updateModules(
    modulesUpdater: (
      currentModules: ConfiguredConstitutionModule[]
    ) => ConfiguredConstitutionModule[]
  ) {
    const currentSessionId = sessionStore.activeSessionId; // Use direct access
    if (!currentSessionId) {
      console.warn(
        "RunConfigurationPanel: No active session ID found, cannot update modules."
      );
      return;
    }
    const currentSession = currentSessionId
      ? sessionStore.uiSessions[currentSessionId]
      : null;
    const activeThreadConfigId = activeStore.activeConfigEditorId; // Use activeStore
    if (!activeThreadConfigId) {
      console.warn(
        "RunConfigurationPanel: No active thread config ID found, cannot update modules."
      );
      return;
    }

    // Use direct access
    if (
      currentSessionId &&
      sessionStore.uiSessions[currentSessionId]?.threads?.[activeThreadConfigId]
    ) {
      const sessionToUpdate = sessionStore.uiSessions[currentSessionId];
      const threadToUpdate = sessionToUpdate.threads[activeThreadConfigId];

      if (!threadToUpdate.runConfig) {
        threadToUpdate.runConfig = { configuredModules: [] };
      }
      const currentModules = threadToUpdate.runConfig.configuredModules ?? [];
      const newModules = modulesUpdater(currentModules);

      if (JSON.stringify(currentModules) !== JSON.stringify(newModules)) {
        const updatedThread = {
          ...threadToUpdate,
          runConfig: {
            ...threadToUpdate.runConfig,
            configuredModules: newModules,
          },
        };
        const updatedSession = {
          ...sessionToUpdate,
          threads: {
            ...sessionToUpdate.threads,
            [activeThreadConfigId]: updatedThread,
          },
          lastUpdatedAt: new Date().toISOString(),
        };
        sessionStore.uiSessions = {
          ...sessionStore.uiSessions,
          [currentSessionId]: updatedSession,
        }; // Use direct access (setter)
        console.log(
          `RunConfigurationPanel: Updated modules for session ${currentSessionId}, thread ${activeThreadConfigId}`
        );
      }
    } else {
      console.warn(
        `RunConfigurationPanel: Could not find session ${currentSessionId} or thread ${activeThreadConfigId} in store to update modules.`
      );
    }
  }

  // Specific handler for checkbox changes
  function handleCheckboxChange(itemId: string, isChecked: boolean) {
    updateModules((currentModules) => {
      if (isChecked) {
        // Add if not present
        if (!currentModules.some((m) => m.id === itemId)) {
          const globalItem = globalConstitutionsList.find(
            (c) => c.id === itemId
          );
          const localItem = localConstitutionsStore.localConstitutions.find(
            (c) => c.id === itemId
          ); // Use direct access
          const title =
            globalItem?.title ?? localItem?.title ?? "Unknown Constitution"; // Provide a default title
          return [
            ...currentModules,
            { id: itemId, title: title, adherence_level: 3 },
          ]; // Add with default level 3
        }
        return currentModules; // Already present, do nothing (level handled by slider)
      } else {
        // Remove if present
        return currentModules.filter((m) => m.id !== itemId);
      }
    });
  }

  // Specific handler for slider input changes
  function handleSliderInput(itemId: string, newLevel: number) {
    updateModules((currentModules) =>
      currentModules.map((m) =>
        m.id === itemId ? { ...m, adherence_level: newLevel } : m
      )
    );
  }

  // Effect to ensure a default config is selected if the active one becomes invalid
  $effect(() => {
    // Derive dependencies directly inside the effect
    const activeSessionId = sessionStore.activeSessionId;
    const activeSession = activeSessionId
      ? sessionStore.uiSessions[activeSessionId]
      : null;
    const currentEditorId = activeStore.activeConfigEditorId;
    const sessionThreads = activeSession?.threads;

    if (sessionThreads) {
      const threadIds = Object.keys(sessionThreads);
      if (threadIds.length > 0) {
        const isValidEditorId =
          currentEditorId !== null &&
          sessionThreads[currentEditorId] !== undefined;
        if (!isValidEditorId) {
          // If current editor ID is null or invalid for the current session, select the first one
          activeStore.setActiveConfigEditor(threadIds[0]);
          console.log(
            `[RunConfigPanel] Defaulting activeConfigEditorId to first thread: ${threadIds[0]}`
          );
        }
      } else {
        // No threads in the active session, ensure editor ID is null
        if (currentEditorId !== null) {
          activeStore.setActiveConfigEditor(null);
        }
      }
    } else {
      // No active session, ensure editor ID is null
      if (currentEditorId !== null) {
        activeStore.setActiveConfigEditor(null);
      }
    }
  });
</script>

<div class="selector-card">
  <!-- Header with integrated toggle -->
  <div
    class="selector-header"
    onclick={toggleExpand}
    role="button"
    tabindex="0"
    onkeydown={(e) => e.key === "Enter" && toggleExpand()}
  >
    <span class="header-title">Flow Configurations</span>
    {#if isExpanded}
      <IconChevronDown class="toggle-icon" />
    {:else}
      <IconChevronUp class="toggle-icon" />
    {/if}
  </div>

  <!-- Collapsible content area -->
  {#if isExpanded}
    <RunConfigManager />

    <div class="options-container">
      {#if isLoadingGlobal}
        <p class="loading-text">Loading global constitutions...</p>
      {:else if globalErrorMsg}
        <p class="loading-text error-text">
          Error loading: {globalErrorMsg}
        </p>
      {:else}
        <div class="options-wrapper">
          <!-- === Add New Constitution Item === -->
          <div
            class="option-item add-item"
            onclick={() => (showAddModal = true)}
            role="button"
            tabindex="0"
            onkeydown={(e) => {
              if (e.key === "Enter" || e.key === " ") showAddModal = true;
            }}
          >
            <div class="option-label add-label">
              <IconAdd class="add-icon" />
              <span class="title-text">Add Constitution</span>
            </div>
          </div>

          <!-- === Local Constitutions List === -->
          {#each localConstitutionsStore.localConstitutions as item (item.id)}
            <!-- Removed @const isSelected -->
            <div class="option-item">
              <label class="option-label">
                <input
                  type="checkbox"
                  checked={!!getModule(item.id)}
                  onchange={(e) =>
                    handleCheckboxChange(item.id, e.currentTarget.checked)}
                />
                <span class="title-text"
                  ><span class="local-indicator">Local</span>{item.title}</span
                >
                <button
                  class="info-button"
                  title="Show constitution info"
                  onclick={(e) => {
                    e.stopPropagation();
                    showInfo(item);
                  }}><IconInfo /></button
                >
              </label>
              {#if getModule(item.id)}
                <div class="slider-container">
                  <input
                    type="range"
                    min="1"
                    max="5"
                    step="1"
                    value={getModule(item.id)?.adherence_level ?? 0}
                    oninput={(e) =>
                      handleSliderInput(item.id, e.currentTarget.valueAsNumber)}
                    class="adherence-slider"
                    aria-label="{item.title} Adherence Level"
                  />
                  <span class="level-display"
                    >{getModule(item.id)?.adherence_level ?? "-"}/5</span
                  >
                </div>
              {/if}
            </div>
          {/each}

          <!-- === Global Constitutions List === -->
          {#each globalConstitutionsList as item (item.id)}
            <!-- Removed @const isSelected -->
            <div class="option-item">
              <label class="option-label">
                <input
                  type="checkbox"
                  checked={!!getModule(item.id)}
                  onchange={(e) =>
                    handleCheckboxChange(item.id, e.currentTarget.checked)}
                />
                <span class="title-text" title={item.description}
                  >{item.title}</span
                >
                <button
                  class="info-button"
                  title="Show constitution info"
                  onclick={(e) => {
                    e.stopPropagation();
                    showInfo(item);
                  }}><IconInfo /></button
                >
              </label>
              {#if getModule(item.id)}
                <div class="slider-container">
                  <input
                    type="range"
                    min="1"
                    max="5"
                    step="1"
                    value={getModule(item.id)?.adherence_level ?? 0}
                    oninput={(e) =>
                      handleSliderInput(item.id, e.currentTarget.valueAsNumber)}
                    class="adherence-slider"
                    aria-label="{item.title} Adherence Level"
                  />
                  <span class="level-display"
                    >{getModule(item.id)?.adherence_level ?? "-"}/5</span
                  >
                </div>
              {/if}
            </div>
          {/each}

          <!-- === Empty State === -->
          {#if globalConstitutionsList.length === 0 && localConstitutionsStore.localConstitutions.length === 0}
            <p class="loading-text">No constitutions available.</p>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- === Modals === -->
{#if showInfoModal}
  <ConstitutionInfoModal
    title={modalTitle}
    description={modalDescription}
    content={modalContent}
    isLoading={modalIsLoading}
    error={modalError}
    onClose={() => (showInfoModal = false)}
  />
{/if}

{#if showAddModal}
  <AddConstitutionModal
    onClose={() => (showAddModal = false)}
  />
{/if}

<style lang="scss">
  @use "../styles/mixins" as *;

  .selector-card {
    @include base-card(); // Use mixin
    overflow: hidden;
    margin-bottom: var(--space-sm);
    transition: all 0.2s ease;
  }

  .selector-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-sm) var(--space-md);
    cursor: pointer;
    border-bottom: 1px solid var(--input-border); /* Separator when expanded */
    background-color: var(--bg-elevated); /* Slightly different header bg */
    transition: background-color 0.2s ease;
  }
  .selector-header:hover {
    background-color: var(--primary-lightest);
  }

  .header-title {
    font-weight: 600; /* Make header title bolder */
    font-size: 0.9em;
    color: var(--text-primary);
  }


  .options-container {
    padding: var(--space-sm) var(--space-md);
    max-height: 350px; /* Further increased height */
    overflow-y: auto;
    @include custom-scrollbar(
      $track-bg: var(--bg-surface),
      $thumb-bg: var(--primary-light),
      $width: 6px
    ); // Use mixin
  }

  // Scrollbar styles handled by mixin above

  .options-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .option-item {
    display: grid;
    grid-template-columns: minmax(150px, 3fr) minmax(100px, 1fr);
    gap: var(--space-xs) var(--space-md);
    align-items: center;
    padding: var(--space-xs); /* Add padding for hover effect */
    border-radius: var(--radius-sm); /* Rounded corners for hover */
    transition: background-color 0.15s ease; /* Smooth hover transition */
  }
  .option-item:hover {
    background-color: rgba(128, 128, 128, 0.1); /* Subtle hover background */
  }

  .option-label {
    grid-column: 1 / 2;
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    cursor: pointer;
    transition: color 0.2s ease;
    overflow: hidden; /* Let the container handle overflow */
  }
  .option-label:hover .title-text {
    /* Target title text on hover */
    color: var(--primary);
  }
  .option-label input[type="checkbox"] {
    cursor: pointer;
    accent-color: var(--primary);
    flex-shrink: 0;
  }
  .title-text {
    /* Allow title to take space but truncate */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex-grow: 1; /* Allow text to grow */
    margin-right: var(--space-xs);
  }
  .info-button {
    @include icon-button($padding: 0); // Use mixin, override padding
    flex-shrink: 0; // Keep specific flex-shrink
    opacity: 0.6; // Keep specific initial opacity

    &:hover {
      // Keep specific hover styles (only color/opacity change)
      color: var(--primary);
      opacity: 1;
      background-color: transparent; // Prevent mixin hover background
    }
  }

  /* Add constitution item styles */
  .add-item {
    cursor: pointer;
    grid-template-columns: 1fr; /* Use a single column for the add item */
  }

  .add-label {
    grid-column: 1 / -1;
    color: var(--primary);
  }


  .slider-container {
    grid-column: 2 / 3;
    display: flex;
    align-items: center;
    gap: var(--space-sm);
  }

  .adherence-slider {
    flex-grow: 1; /* Allow slider to take available space */
    cursor: pointer;
    accent-color: var(--primary);
    height: 8px; /* Make slider visually smaller */
  }

  .level-display {
    font-size: 0.8em;
    color: var(--text-secondary);
    min-width: 25px; /* Ensure space for "X/5" */
    text-align: right;
  }

  .loading-text {
    font-style: italic;
    color: var(--text-secondary);
    padding: var(--space-md);
    text-align: center;
  }

  .local-indicator {
    font-weight: 600;
    color: var(--secondary); /* Or another distinct color */
    margin-right: var(--space-xs);
    border: 1px solid var(--secondary);
    border-radius: var(--radius-sm);
    margin: 0 var(--space-xs);
    padding: 0 var(--space-xs);
    font-size: 0.9em;
  }
</style>

<script lang="ts">
  import {
    fetchConstitutionContent,
  } from "$lib/api/rest.svelte";
  import { activeStore } from "$lib/state/active.svelte";
  import { constitutionStore } from "$lib/state/constitutions.svelte"; // Use the unified store
  import { sessionStore } from "$lib/state/session.svelte";

  import IconAdd from "~icons/fluent/add-24-regular";
  import IconChevronDown from "~icons/fluent/chevron-down-24-regular";
  import IconChevronUp from "~icons/fluent/chevron-up-24-regular";
  import IconInfo from "~icons/fluent/info-24-regular";
  
  import AddConstitutionModal from "./AddConstitutionModal.svelte";
  import ConstitutionInfoModal from "./ConstitutionInfoModal.svelte";
  import RunConfigManager from "./RunConfigManager.svelte";
  import ConstitutionNode from './ConstitutionNode.svelte'; // <-- Added import

  let isExpanded = $state(true);
  let showInfoModal = $state(false);
  let modalIsLoading = $state(false);
  let modalError: string | null = $state(null);
  let modalTitle: string = $state("");
  let modalDescription: string | undefined = $state(undefined);
  let modalContent: string | undefined = $state(undefined);
  let showAddModal = $state(false);
  let expandedFolderPaths = $state(new Set<string>(['local'])); // State for expanded folders, 'local' expanded by default

  // --- Derived State for Selected Paths ---

  async function showInfo(item: LocalConstitutionMetadata | RemoteConstitutionMetadata) {
    modalTitle = item.title;
    const isRemote = item.source === 'remote';

    modalDescription = isRemote
      ? item.description ?? `Remote constitution (${item.relativePath})`
      : `Local constitution`;
    modalContent = undefined;
    modalError = null;
    modalIsLoading = true;
    showInfoModal = true;

    if (!isRemote) {
      modalContent = item.text; 
      modalIsLoading = false;
    } else {
      // For remote, fetch content using relativePath
      try {
        modalContent = await fetchConstitutionContent(item.relativePath);
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

  // Handles toggling expansion state for folders in the tree
  function handleToggleExpand(node: UIFolderNode) {
    const newSet = new Set(expandedFolderPaths);
    if (newSet.has(node.uiPath)) {
      newSet.delete(node.uiPath);
    } else {
      newSet.add(node.uiPath);
    }
    expandedFolderPaths = newSet;
  }

  // --- Reactive Derived State ---
  let activeSessionId = $derived(sessionStore.activeSessionId);
  let activeThreadConfigId = $derived(activeStore.activeConfigEditorId);
  let currentSession = $derived(activeSessionId ? sessionStore.uiSessions[activeSessionId] : null);
  let threadToUpdate = $derived(currentSession && activeThreadConfigId ? currentSession.threads[activeThreadConfigId] : null);
  let currentModules = $derived(threadToUpdate?.runConfig?.configuredModules ?? []);

  // --- Event Handlers ---

  function handleToggleSelect(uiPath: string, isSelected: boolean, metadata: LocalConstitutionMetadata | RemoteConstitutionMetadata) {
    // Use derived state variables directly
    if (!activeSessionId || !activeThreadConfigId || !currentSession || !threadToUpdate) {
      console.warn("RunConfigurationPanel: Cannot handle toggle select - missing active session/thread context.");
      return;
    }

    if (!threadToUpdate.runConfig) {
        threadToUpdate.runConfig = { configuredModules: [] };
    }

    if (isSelected) {
      // Add if not present, identified by title
      const alreadyExists = currentModules.some((m) => m.title === metadata.title);

      if (!alreadyExists) {
        // Construct the correct module type based on source
        const newModule: ConfiguredConstitutionModule =
          metadata.source === 'remote'
            ? { relativePath: metadata.relativePath, title: metadata.title, adherence_level: 3 }
            : { text: metadata.text, title: metadata.title, adherence_level: 3 };
        threadToUpdate.runConfig.configuredModules.push(newModule);
        currentSession.lastUpdatedAt = new Date().toISOString(); 
      }
    } else {
      // Remove based on title using filter (creates new array, assign back)
      const initialLength = currentModules.length;
      threadToUpdate.runConfig.configuredModules = currentModules.filter((m) => m.title !== metadata.title);
      if (threadToUpdate.runConfig.configuredModules.length !== initialLength) {
          currentSession.lastUpdatedAt = new Date().toISOString(); // Update timestamp only if removed
      }
    }
  }

  function findMetadataInTree(uiPath: string, nodes: UINode[]): LocalConstitutionMetadata | RemoteConstitutionMetadata | null {
    for (const node of nodes) {
      if (node.type === 'file' && node.uiPath === uiPath) {
        return node.metadata;
      } else if (node.type === 'folder') {
        const found = findMetadataInTree(uiPath, node.children);
        if (found) {
          return found;
        }
      }
    }
    return null;
  }

  function handleSliderInput(uiPath: string, newLevel: number) {
    const metadata = findMetadataInTree(uiPath, constitutionStore.displayTree);
    if (!metadata) {
      console.error(`[RunConfigurationPanel] Could not find metadata for uiPath ${uiPath} in handleSliderInput`);
      return;
    }

    if (!activeSessionId || !activeThreadConfigId || !currentSession || !threadToUpdate) {
       console.warn(`RunConfigurationPanel: Could not find session/thread context for slider input.`);
       return;
    }
    if (!threadToUpdate.runConfig?.configuredModules) {
        console.warn(`[RunConfigurationPanel] runConfig or configuredModules missing for slider input on thread ${activeThreadConfigId}.`);
        return;
    }

    const moduleIndex = currentModules.findIndex((m) => m.title === metadata.title);

    if (moduleIndex !== -1) {
        currentModules[moduleIndex].adherence_level = newLevel;
        currentSession.lastUpdatedAt = new Date().toISOString();
    } else {
        console.warn(`[RunConfigurationPanel] Could not find module with title "${metadata.title}" to update level.`);
    }
  }

  // Effect to ensure a default config is selected if the active one becomes invalid
  $effect(() => {
    const activeSessionId = sessionStore.activeSessionId;
    const activeSession = activeSessionId ? sessionStore.uiSessions[activeSessionId] : null;
    const currentEditorId = activeStore.activeConfigEditorId;
    const sessionThreads = activeSession?.threads;

    if (sessionThreads) {
      const threadIds = Object.keys(sessionThreads);
      if (threadIds.length > 0) {
        const isValidEditorId = currentEditorId !== null && sessionThreads[currentEditorId] !== undefined;
        if (!isValidEditorId) {
          activeStore.setActiveConfigEditor(threadIds[0]);
          console.log(`[RunConfigPanel] Defaulting activeConfigEditorId to first thread: ${threadIds[0]}`);
        }
      } else {
        if (currentEditorId !== null) activeStore.setActiveConfigEditor(null);
      }
    } else {
      if (currentEditorId !== null) activeStore.setActiveConfigEditor(null);
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
      <!-- Use constitutionStore for loading/error state -->
      {#if constitutionStore.isLoadingGlobal}
        <p class="loading-text">Loading constitutions...</p>
      {:else if constitutionStore.globalError}
        <p class="loading-text error-text">Error: {constitutionStore.globalError}</p>
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
              <span class="title-text">Add a Constitution</span>
            </div>
          </div>

          <!-- === Hierarchical Constitution Tree === -->
          {#each constitutionStore.displayTree as node (node.uiPath)}
            {@const isSelected = node.type === 'file' && currentModules.some(m => m.title === node.metadata.title)}
            <ConstitutionNode
              node={node}
              level={0}
              isSelected={isSelected}
              activeConfigModules={currentModules} 
              {expandedFolderPaths}
              getModule={(uiPath: string) => currentModules.find(m => {
                  const meta = findMetadataInTree(uiPath, constitutionStore.displayTree);
                  return meta ? m.title === meta.title : false;
              }) ?? null}
              onToggleSelect={handleToggleSelect}
              onShowDetail={showInfo}
              onSliderInput={handleSliderInput}
              onToggleExpand={handleToggleExpand}
            />
          {/each}
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
    // grid-template-columns: minmax(150px, 3fr) minmax(100px, 1fr); // Removed old grid layout
    gap: var(--space-xs) var(--space-md);
    align-items: center;
    padding: var(--space-xs); /* Add padding for hover effect */
    border-radius: var(--radius-sm); /* Rounded corners for hover */
    transition: background-color 0.15s ease; /* Smooth hover transition */
  }
  .option-item:hover {
    // background-color: rgba(128, 128, 128, 0.1); /* Subtle hover background - Handled by Node */
  }

  .option-label {
    // grid-column: 1 / 2; // Removed old grid layout
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
    // grid-column: 2 / 3; // Removed old grid layout
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
</style>

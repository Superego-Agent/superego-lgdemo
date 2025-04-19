<script lang="ts">
  import { apiKeyStore, setApiKey } from '../state/apiKey.svelte.ts';
  import { sendApiKeyToBackend } from '../services/apiKey.svelte';
  import { activeStore } from '$lib/state/active.svelte';
  import IconEye from "~icons/fluent/eye-24-regular";
  import IconEyeOff from "~icons/fluent/eye-off-24-regular";
  import IconInfo from "~icons/fluent/info-24-regular";
  import IconDelete from "~icons/fluent/delete-24-regular";
  import IconCheck from "~icons/fluent/checkmark-24-regular";
  import IconError from "~icons/fluent/error-circle-24-regular";

  // Component state
  let apiKey = $state('');
  let showApiKey = $state(false);
  let isTooltipVisible = $state(false);
  let isSending = $state(false);
  let sendStatus = $state<'idle' | 'success' | 'error'>('idle');
  let statusMessage = $state('');

  // Subscribe to the store to update the component when the store changes
  $effect(() => {
    const unsubscribe = apiKeyStore.subscribe(value => {
      apiKey = value;
    });
    
    return unsubscribe;
  });

  // Update the store when the input changes
  function handleInputChange() {
    setApiKey(apiKey); // Use setApiKey to update both stores
    // Reset status when the key changes
    sendStatus = 'idle';
    statusMessage = '';
  }

  // Send the API key to the backend
  async function sendApiKey() {
    if (!apiKey) {
      activeStore.setGlobalError('Please enter an API key');
      return;
    }

    isSending = true;
    sendStatus = 'idle';
    statusMessage = '';

    try {
      const result = await sendApiKeyToBackend();
      sendStatus = 'success';
      statusMessage = result.message || 'API key sent successfully';
    } catch (error) {
      sendStatus = 'error';
      statusMessage = error instanceof Error ? error.message : 'Failed to send API key';
    } finally {
      isSending = false;
    }
  }

  // Toggle visibility of the API key
  function toggleVisibility() {
    showApiKey = !showApiKey;
  }

  // Clear the API key
  function clearApiKey() {
    apiKey = '';
    setApiKey(''); // Use setApiKey to clear both stores
    sendStatus = 'idle';
    statusMessage = '';
  }

  // Show/hide tooltip
  function showTooltip() {
    isTooltipVisible = true;
  }

  function hideTooltip() {
    isTooltipVisible = false;
  }
</script>

<div class="api-key-container">
  <div class="api-key-header">
    <label for="api-key-input">Enter your Anthropic API Key here</label>
    <div 
      class="info-icon" 
      on:mouseenter={showTooltip} 
      on:mouseleave={hideTooltip}
      on:focus={showTooltip}
      on:blur={hideTooltip}
      tabindex="0"
    >
      <IconInfo />
      {#if isTooltipVisible}
        <div class="tooltip">
          This API key is stored in memory only and will be cleared when you refresh or close the page.
        </div>
      {/if}
    </div>
  </div>
  
  {#if activeStore.globalError && activeStore.globalError.includes('API key')}
    <div class="api-key-required-message">
      <IconError />
      <span>{activeStore.globalError}</span>
    </div>
  {/if}
  
  <div class="input-group">
    <input 
      id="api-key-input"
      type={showApiKey ? "text" : "password"}
      placeholder="Enter API key"
      bind:value={apiKey}
      on:input={handleInputChange}
      class="api-key-input"
    />
    
    <button 
      type="button" 
      class="icon-button visibility-toggle" 
      on:click={toggleVisibility}
      title={showApiKey ? "Hide API key" : "Show API key"}
    >
      {#if showApiKey}
        <IconEyeOff />
      {:else}
        <IconEye />
      {/if}
    </button>
    
    {#if apiKey}
      <button 
        type="button" 
        class="icon-button clear-button" 
        on:click={clearApiKey}
        title="Clear API key"
      >
        <IconDelete />
      </button>
    {/if}
  </div>

  <div class="api-key-actions">
    <button 
      type="button" 
      class="send-button" 
      on:click={sendApiKey}
      disabled={!apiKey || isSending}
    >
      {#if isSending}
        Sending...
      {:else}
        Set API Key
      {/if}
    </button>

    {#if sendStatus === 'success'}
      <div class="status-message success">
        <IconCheck />
        <span>{statusMessage}</span>
      </div>
    {:else if sendStatus === 'error'}
      <div class="status-message error">
        <IconError />
        <span>{statusMessage}</span>
      </div>
    {/if}
  </div>
</div>

<style lang="scss">
  .api-key-container {
    margin-bottom: var(--space-md);
    padding: var(--space-sm);
    border-radius: var(--radius-md);
    background-color: var(--bg-elevated);
  }

  .api-key-header {
    display: flex;
    align-items: center;
    margin-bottom: var(--space-xs);
    
    label {
      font-size: 0.9em;
      font-weight: 500;
      color: var(--text-secondary);
      margin-right: var(--space-xs);
    }
  }

  .info-icon {
    position: relative;
    display: inline-flex;
    color: var(--text-secondary);
    cursor: pointer;
    
    &:hover, &:focus {
      color: var(--primary);
    }
  }

  .tooltip {
    position: absolute;
    top: 100%;
    left: 0;
    width: 250px;
    padding: var(--space-xs);
    background-color: var(--bg-surface);
    border: 1px solid var(--input-border);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-md);
    font-size: 0.8em;
    color: var(--text-primary);
    z-index: 100;
    margin-top: var(--space-xs);
  }

  .input-group {
    display: flex;
    align-items: center;
    position: relative;
  }

  .api-key-input {
    flex: 1;
    padding: var(--space-sm);
    padding-right: calc(var(--space-sm) * 2 + 24px); /* Make room for the buttons */
    border: 1px solid var(--input-border);
    border-radius: var(--radius-sm);
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-size: 0.9em;
    
    &:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 1px var(--primary-light);
    }
    
    &::placeholder {
      color: var(--text-tertiary);
    }
  }

  .icon-button {
    position: absolute;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-secondary);
    padding: 4px;
    transition: color 0.2s ease;
    
    &:hover, &:focus {
      color: var(--primary);
    }
  }

  .visibility-toggle {
    right: 4px;
  }

  .clear-button {
    right: 28px;
    
    &:hover, &:focus {
      color: var(--error);
    }
  }

  .api-key-actions {
    margin-top: var(--space-sm);
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
  }

  .send-button {
    padding: var(--space-xs) var(--space-sm);
    background-color: var(--primary);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.9em;
    transition: background-color 0.2s ease;
    
    &:hover:not(:disabled) {
      background-color: var(--primary-dark);
    }
    
    &:disabled {
      background-color: var(--primary-light);
      cursor: not-allowed;
      opacity: 0.7;
    }
  }

  .status-message {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: 0.8em;
    padding: var(--space-xs);
    border-radius: var(--radius-sm);
    
    &.success {
      background-color: var(--success-bg);
      color: var(--success);
    }
    
    &.error {
      background-color: var(--error-bg);
      color: var(--error);
    }
  }
  
  .api-key-required-message {
    display: flex;
    align-items: center;
    gap: var(--space-xs);
    font-size: 0.9em;
    padding: var(--space-sm);
    margin-bottom: var(--space-sm);
    border-radius: var(--radius-sm);
    background-color: var(--error-bg);
    color: var(--error);
    border-left: 3px solid var(--error);
  }
</style>

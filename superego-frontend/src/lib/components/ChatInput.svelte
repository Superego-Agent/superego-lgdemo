<script lang="ts">
  import { isLoading } from "../stores";
  import { scale } from "svelte/transition";
  import { createEventDispatcher } from "svelte";

  // Import icons - Reverting to Send icon
  import IconSend from '~icons/fluent/send-24-regular';
  // import IconEdit from '~icons/fluent/edit-24-regular'; // Using Edit icon for test
  import IconLoading from '~icons/fluent/arrow-sync-circle-24-regular';


  let userInput: string = "";
  let inputElement: HTMLTextAreaElement;
  let isExpanded = false;

  // Initialize dispatcher without explicit generic type for testing
  const dispatch = createEventDispatcher();

  function handleSubmit() {
    const trimmedInput = userInput.trim();
    if (!trimmedInput || $isLoading) {
      console.log("Submit prevented: input empty or loading."); // Line 38 area
      return;
    }

    console.log("Dispatching send event with:", trimmedInput);
    dispatch("send", { text: trimmedInput });

    userInput = "";
    isExpanded = false;
    inputElement?.style.setProperty("height", "auto");
  }

  function handleFocus() {
    isExpanded = true;
  }

  function handleBlur() {
    setTimeout(() => {
      if (!userInput.trim()) {
        isExpanded = false;
      }
    }, 150);
  }

  function handleInput() {
    if (inputElement) {
      inputElement.style.setProperty("height", "auto");
      const maxHeight = 150;
      const scrollHeight = inputElement.scrollHeight;
      inputElement.style.setProperty(
        "height",
        `${Math.min(scrollHeight, maxHeight)}px`
      );
    }
  }
</script>

<form
  class="chat-input-form"
  class:expanded={isExpanded}
  on:submit|preventDefault={handleSubmit}
>
  <div class="textarea-container">
    <textarea
      bind:this={inputElement}
      bind:value={userInput}
      placeholder="Send a message..."
      rows={isExpanded ? 3 : 1}
      disabled={$isLoading}
      on:focus={handleFocus}
      on:blur={handleBlur}
      on:input={handleInput}
      on:keydown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          handleSubmit();
        }
      }}
    ></textarea>
  </div>

  <!-- Restore conditional logic and loading class -->
  <button
    type="submit"
    disabled={!userInput.trim() || $isLoading}
    class:loading={$isLoading}
    title="Send Message"
    in:scale|local={{ duration: 150, start: 0.8 }}>

    {#if $isLoading}
      <IconLoading class="loading-icon-animate" />
    {:else}
      <IconSend />
    {/if}
  </button>
</form>

<style>
  .chat-input-form {
    display: flex;
    padding: var(
      --space-md
    ); /* border-top: 1px solid var(--input-border); */ /* background-color: var(--bg-surface); */
    gap: var(--space-md);
    transition: padding 0.2s ease;
    align-items: flex-end;
  }
  .chat-input-form.expanded {
    padding: var(--space-lg) var(--space-md);
  }
  .textarea-container {
    flex-grow: 1;
    position: relative;
    box-shadow: var(--shadow-sm);
    border-radius: var(--radius-lg);
    transition: all 0.3s ease;
    border: 1px solid var(--input-border);
    background-color: white;
  }
  .expanded .textarea-container {
    box-shadow: var(--shadow-md);
  }
  textarea {
    width: 100%;
    padding: var(--space-md) var(--space-lg);
    padding-right: calc(var(--space-lg) + 10px);
    border: none; /* REMOVED border */
    background-color: transparent; /* Make textarea bg transparent */
    color: var(--text-primary);
    border-radius: var(--radius-lg);
    resize: none;
    font-family: inherit;
    font-size: 1em;
    line-height: 1.4;
    max-height: 150px;
    transition: all 0.2s ease;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--primary-light) transparent;
  }
  textarea::-webkit-scrollbar {
    width: 6px;
  }
  textarea::-webkit-scrollbar-track {
    background: transparent;
  }
  textarea::-webkit-scrollbar-thumb {
    background-color: var(--primary-light);
    border-radius: var(--radius-pill);
  }
  .textarea-container:has(textarea:focus) {
    border-color: var(--input-focus);
    outline: none;
    box-shadow:
      var(--shadow-md),
      0 0 0 2px rgba(157, 70, 255, 0.2);
  }
  textarea:focus {
    outline: none; /* Remove default textarea focus outline */
  }
  textarea:disabled {
    background-color: var(--bg-surface);
    cursor: not-allowed;
    opacity: 0.7;
  }
  /* Minimal button styling + ONLY CIRCULAR shape */
  button {
      padding: 0; /* Remove padding for fixed size */
      height: 44px; /* Set fixed height */
      width: 44px; /* Set fixed width */
      cursor: pointer;
      align-self: flex-end; /* Keep alignment */
      margin-bottom: var(--space-sm); /* Adjust margin as needed */
      /* Basic appearance */
      background-color: #eee;
      border: 1px solid #ccc;
      border-radius: var(--radius-pill); /* Make it circular */
      color: #333; /* Default text/icon color for basic button */
      /* Ensure icon fits */
      display: flex;
      align-items: center;
      justify-content: center;
      line-height: 1; /* Prevent extra space */
  }
   button:disabled {
       cursor: not-allowed;
       opacity: 0.6;
       background-color: #f5f5f5; /* Basic disabled background */
       color: #999; /* Basic disabled text/icon color */
   }
   /* Remove hover/loading styles */

  /* Keep loading animation definition */
   .loading-icon-animate {
       animation: spin 1s linear infinite;
   }
  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }
  @media (max-width: 768px) {
    /* Existing mobile styles */
  }
</style>

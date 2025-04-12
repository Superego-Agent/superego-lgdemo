<script lang="ts">
  import { scale } from "svelte/transition";

  import IconLoading from '~icons/fluent/arrow-sync-circle-24-regular';
  import IconSend from '~icons/fluent/send-24-regular';

  // --- Component State ---
  let userInput: string = $state("");
  let inputElement: HTMLTextAreaElement | null = $state(null);
  let isExpanded = $state(false);

  // --- Props ---
  
  interface Props {
    /** Controls whether the input and button are disabled. Passed from parent. */
    disabled?: boolean;
    onSend?: (detail: { text: string }) => void;
  }

  let { disabled = false, onSend = () => {} }: Props = $props();

  // --- Dispatcher ---

  // --- Event Handlers & Logic ---
  function handleSubmit() {
    const trimmedInput = userInput.trim();
    if (!trimmedInput || disabled) {
      return;
    }

    onSend({ text: trimmedInput });

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
  onsubmit={(e) => {e.preventDefault(); handleSubmit()}}
>
  <!-- Text Input Area -->
  <div class="textarea-container">
    <textarea
      bind:this={inputElement}
      bind:value={userInput}
      placeholder="Type your message here..."
      rows={isExpanded ? 3 : 1}
      disabled={disabled}
      onfocus={handleFocus}
      onblur={handleBlur}
      oninput={handleInput}
      onkeydown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          handleSubmit();
        }
      }}
    ></textarea>
  </div>

  <!-- Submit Button (Shows Loading/Send Icon) -->
  <button
    type="submit"
    disabled={!userInput.trim() || disabled}
    class:loading={disabled}
    title="Send Message"
    in:scale|local={{ duration: 150, start: 0.8 }}>

    {#if disabled}
      <IconLoading class="loading-icon-animate" />
    {:else}
      <IconSend />
    {/if}
  </button>
</form>

<style lang="scss">
  @use '../styles/mixins' as *;

  .chat-input-form {
    width: 100%;
    margin: 0px;
    padding: 0px;
    display: flex;
    gap: var(--space-md);
    transition: all 0.2s ease;
    align-items: space-between;
    justify-content: center;
  }
  .chat-input-form.expanded {

    padding: 0px;
  }
  .textarea-container {
    flex-grow: 1;
    position: relative;
    box-shadow: var(--shadow-sm);
    border-radius: var(--radius-lg);
    transition: all 0.3s ease;
    border: 1px solid var(--input-border);
    background-color: var(--input-bg);
  }
  .expanded .textarea-container {
    box-shadow: var(--shadow-md);
  }
  textarea {
    width: 100%;
    padding: var(--space-md) var(--space-lg);
    padding-right: calc(var(--space-lg) + 10px);
    border: none;
    background-color: transparent;
    color: var(--text-primary);
    border-radius: var(--radius-lg);
    resize: none;
    font-family: inherit;
    font-size: 1em;
    line-height: 1.4;
    max-height: 150px;
    transition: all 0.2s ease;
    overflow-y: auto;
    @include custom-scrollbar($track-bg: transparent, $thumb-bg: var(--primary-light), $width: 6px); // Use mixin
  }

  // Style the container when the textarea inside it is focused
  .textarea-container:has(:global(textarea:focus)) {
    border-color: var(--input-focus);
    outline: none;
    box-shadow:
      var(--shadow-md),
      0 0 0 2px rgba(157, 70, 255, 0.2);
  }
  textarea:focus {
    outline: none;
  }
  textarea:disabled {
    background-color: var(--bg-surface);
    cursor: not-allowed;
    opacity: 0.7;
  }

  button {
      padding: 0;
      height: 44px;
      width: 44px;
      cursor: pointer;
      align-self: flex-end;
      margin-bottom: var(--space-sm);
      background-color: var(--button-bg, #eee); 
      border: 1px solid var(--button-border, #ccc); 
      border-radius: var(--radius-pill);
      color: var(--button-text, #333); 
      display: flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
      transition: background-color 0.2s ease, opacity 0.2s ease, color 0.2s ease;
  }
   button:disabled {
       cursor: not-allowed;
       opacity: var(--button-disabled-opacity, 0.6); 
       background-color: var(--button-disabled-bg, #f5f5f5); 
       color: var(--button-disabled-text, #999);
  }
  button:not(:disabled) {
      background-color: var(--success);
      color: #ffffff; /* White text for contrast on green */
      border-color: transparent; /* Remove border when active */
   }

</style>

<script lang="ts">
    import { isLoading } from '../stores';
    import { scale } from 'svelte/transition';
    import { createEventDispatcher } from 'svelte';

    let userInput: string = '';
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
        // Dispatching remains the same, but type checking is lost temporarily
        dispatch('send', { text: trimmedInput });

        userInput = '';
        isExpanded = false;
        inputElement?.style.setProperty('height', 'auto');
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
             inputElement.style.setProperty('height', 'auto');
             const maxHeight = 150;
             const scrollHeight = inputElement.scrollHeight;
             inputElement.style.setProperty('height', `${Math.min(scrollHeight, maxHeight)}px`);
        }
    }

</script>

<form class="chat-input-form" class:expanded={isExpanded} on:submit|preventDefault={handleSubmit}>
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
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                }
            }}
        ></textarea> </div>

    <button
        type="submit"
        disabled={!userInput.trim() || $isLoading}
        class:loading={$isLoading}
        title="Send Message"
        in:scale|local={{ duration: 150, start: 0.8 }}
    >
        {#if $isLoading}
            <div class="button-spinner"></div>
        {:else}
            <span class="send-icon">↗</span>
        {/if}
    </button>
</form>

<style>
    /* Styles remain unchanged */
    .chat-input-form { display: flex; padding: var(--space-md); border-top: 1px solid var(--input-border); background-color: var(--bg-surface); gap: var(--space-md); transition: padding 0.2s ease; align-items: flex-end; }
    .chat-input-form.expanded { padding: var(--space-lg) var(--space-md); }
    .textarea-container { flex-grow: 1; position: relative; box-shadow: var(--shadow-sm); border-radius: var(--radius-lg); transition: all 0.3s ease; }
    .expanded .textarea-container { box-shadow: var(--shadow-md); }
    textarea { width: 100%; padding: var(--space-md) var(--space-lg); padding-right: calc(var(--space-lg) + 10px); border: 1px solid var(--input-border); background-color: var(--input-bg); color: var(--text-primary); border-radius: var(--radius-lg); resize: none; font-family: inherit; font-size: 1em; line-height: 1.4; max-height: 150px; transition: all 0.2s ease; overflow-y: auto; scrollbar-width: thin; scrollbar-color: var(--primary-light) transparent; }
    textarea::-webkit-scrollbar { width: 6px; }
    textarea::-webkit-scrollbar-track { background: transparent; }
    textarea::-webkit-scrollbar-thumb { background-color: var(--primary-light); border-radius: var(--radius-pill); }
    textarea:focus { border-color: var(--input-focus); outline: none; box-shadow: 0 0 0 2px rgba(157, 70, 255, 0.2); }
    textarea:disabled { background-color: var(--bg-surface); cursor: not-allowed; opacity: 0.7; }
    button { height: 44px; width: 44px; border: none; background-color: var(--primary); color: white; border-radius: var(--radius-pill); cursor: pointer; font-size: 1.2em; transition: all 0.3s ease; display: flex; align-items: center; justify-content: center; box-shadow: var(--shadow-sm); flex-shrink: 0; align-self: flex-end; margin-bottom: calc( (var(--space-md) - 1em * 1.4) / 2 + 1px ); }
    .expanded button { margin-bottom: calc( (var(--space-md) - 1em * 1.4) / 2 + 1px ); }
    button:hover:not(:disabled) { background-color: var(--primary-light); transform: translateY(-2px); box-shadow: var(--shadow-md); }
    button:disabled { background-color: var(--primary-dark); cursor: not-allowed; opacity: 0.6; transform: scale(0.95); }
    button.loading { background-color: var(--primary-dark); }
    .button-spinner { border: 3px solid rgba(255, 255, 255, 0.3); border-top: 3px solid #fff; border-radius: 50%; width: 18px; height: 18px; animation: spin 1s linear infinite; }
    .send-icon { font-weight: bold; transform: rotate(45deg); display: inline-block; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    @media (max-width: 768px) { /* Existing mobile styles */ }
</style>
<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    import AddConstitution from './AddConstitution.svelte';

    const dispatch = createEventDispatcher();

    function closeModal() {
        dispatch('close');
    }

    // Close modal on Escape key press
    function handleKeydown(event: KeyboardEvent) {
        if (event.key === 'Escape') {
            closeModal();
        }
    }
</script>

<svelte:window on:keydown={handleKeydown}/>

<div class="modal-overlay" on:click={closeModal}>
    <div class="modal-content" on:click|stopPropagation>
        <button class="close-button" on:click={closeModal}>&times;</button>
        <AddConstitution on:constitutionAdded={closeModal} />
    </div>
</div>

<style>
    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: rgba(0, 0, 0, 0.6);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000; /* Ensure modal is on top */
    }

    .modal-content {
        background-color: var(--bg-elevated);
        padding: 20px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        position: relative;
        max-width: 600px; /* Adjust as needed */
        width: 90%;
        max-height: 80vh; /* Limit height and allow scrolling if needed */
        overflow-y: auto; /* Add scroll for overflow */
    }

    .close-button {
        position: absolute;
        top: 10px;
        right: 10px;
        background: none;
        border: none;
        font-size: 1.5rem;
        color: var(--text-secondary);
        cursor: pointer;
        line-height: 1;
    }
    .close-button:hover {
        color: var(--text-primary);
    }
</style>

<script lang="ts">
  import AddConstitution from "./AddConstitution.svelte";

  let { onClose = () => {} } = $props<{
    onClose?: () => void;
  }>();

  function closeModal() {
    onClose();
  }

  // Close modal on Escape key press
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      closeModal();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="modal-overlay" onclick={closeModal} role="dialog" aria-modal="true" tabindex="-1">
  <div class="modal-content" onclick={(e) => e.stopPropagation()}>
    <button class="close-button" onclick={closeModal}>&times;</button>
    <AddConstitution onConstitutionAdded={closeModal} onClose={closeModal} />
  </div>
</div>

<style lang="scss">
  @use "../styles/mixins" as *;

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
    @include base-card(
      $bg: var(--bg-elevated),
      $radius: 8px,
      $shadow: 0 4px 15px rgba(0, 0, 0, 0.2)
    ); // Use mixin with overrides
    padding: 20px; // Keep specific padding
    position: relative;
    max-width: 600px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    @include custom-scrollbar(
      $track-bg: var(--bg-elevated)
    ); // Use mixin, override track background
  }

  .close-button {
    @include icon-button($padding: 0); // Use mixin, override padding
    position: absolute;
    top: 10px;
    right: 10px;
    font-size: 1.5rem; // Keep specific size

    &:hover {
      // Override mixin hover
      color: var(--text-primary);
      background-color: transparent; // Ensure no background on hover
    }
  }
</style>

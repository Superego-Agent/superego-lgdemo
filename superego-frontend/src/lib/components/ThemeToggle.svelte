<script lang="ts">
  import { activeStore } from '$lib/state/active.svelte'; // Use $lib alias, remove .ts extension
  import { fade } from 'svelte/transition';

  // Reactive icon based on current theme
  let icon = $derived(activeStore.theme === 'light' ? '🌙' : '☀️');
  let label = $derived(activeStore.theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
</script>

<button 
  class="theme-toggle" 
  onclick={() => activeStore.toggleTheme()}
  title={label} 
  aria-label={label}
>
  <span class="toggle-icon" in:fade={{ duration: 200 }}>{icon}</span>
</button>

<style lang="scss">
  @use '../styles/mixins' as *;

  .theme-toggle {
    @include icon-button($padding: var(--space-sm), $hover-bg: var(--bg-elevated), $hover-color: var(--text-primary)); // Use mixin with specific hover colors
    font-size: 1.2rem; // Keep specific font size
    color: var(--text-primary); // Keep specific initial color

    &:hover {
      // Override mixin hover transform if needed, or add specific ones
      transform: scale(1.1);
    }
  }

  .toggle-icon {
    display: inline-block; // This might be handled by flex centering in mixin, but keep if needed
  }
</style>

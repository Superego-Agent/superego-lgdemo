<script lang="ts">
  import { theme, toggleTheme } from '../stores/theme';
  import { fade } from 'svelte/transition';

  // Reactive icon based on current theme
  $: icon = $theme === 'light' ? '🌙' : '☀️';
  $: label = $theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode';
</script>

<button 
  class="theme-toggle" 
  on:click={toggleTheme} 
  title={label} 
  aria-label={label}
>
  <span class="toggle-icon" in:fade={{ duration: 200 }}>{icon}</span>
</button>

<style>
  .theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: var(--space-sm);
    font-size: 1.2rem;
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    transition: all 0.2s ease;
  }

  .theme-toggle:hover {
    background-color: var(--bg-elevated);
    transform: scale(1.1);
  }

  .toggle-icon {
    display: inline-block;
  }
</style>

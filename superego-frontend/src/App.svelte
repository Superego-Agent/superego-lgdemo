<script lang="ts">
	import { onMount, afterUpdate } from 'svelte';
	import Sidebar from './lib/components/Sidebar.svelte';
	import ChatInterface from './lib/components/ChatInterface.svelte';
	import ThemeToggle from './lib/components/ThemeToggle.svelte';
	import { theme } from './lib/stores/theme';
	import './lib/styles/theme.css';
	import './lib/styles/dark-theme.css';
	
	// Handle theme updates
	$: if (typeof document !== 'undefined') {
		document.documentElement.setAttribute('data-theme', $theme);
	}
	
	// Apply theme on mount
	onMount(() => {
		document.documentElement.setAttribute('data-theme', $theme);
	});
</script>

<main class="app-layout">
	<Sidebar />
	<ChatInterface />
	<div class="theme-toggle-container">
		<ThemeToggle />
	</div>
</main>

<style>
	.app-layout {
		display: flex;
		height: 100%;
		width: 100%;
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		overflow: hidden; /* Prevent layout issues */
		background-color: var(--bg-primary);
	}

    /* Ensure global styles don't interfere too much */
    :global(body) {
        margin: 0;
        padding: 0;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', sans-serif;
        background-color: var(--bg-primary);
        color: var(--text-primary);
        overflow: hidden;
        position: fixed;
        width: 100%;
        height: 100%;
        touch-action: manipulation;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    :global(*, *::before, *::after) {
        box-sizing: border-box;
    }
    
    /* Mobile styles */
    @media (max-width: 768px) {
        .app-layout {
            flex-direction: column;
        }
    }
    
    /* Fix iOS height issues */
    @supports (-webkit-touch-callout: none) {
        .app-layout {
            height: -webkit-fill-available;
        }
    }

	.theme-toggle-container {
		position: fixed;
		top: 12px;
		right: 12px;
		z-index: 100;
	}
	
	@media (max-width: 768px) {
		.theme-toggle-container {
			top: 8px;
			right: 8px;
		}
	}
</style>

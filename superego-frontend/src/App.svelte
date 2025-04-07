<script lang="ts">
    import { onMount } from 'svelte';
    // Removed get, managedConversations, activeConversationId imports
    import Sidebar from './lib/components/Sidebar.svelte';
    import ChatInterface from './lib/components/ChatInterface.svelte';
    import ThemeToggle from './lib/components/ThemeToggle.svelte';
    import { theme } from './lib/stores/theme';
    import { fetchConstitutions } from './lib/api';
    import './lib/styles/theme.css';
    import './lib/styles/dark-theme.css';

    // Handle theme updates reactively
    $: if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', $theme);
    }

    // Apply theme and fetch initial data on mount
    onMount(async () => {
        document.documentElement.setAttribute('data-theme', $theme);
        try {
            // Fetch essential data
            await fetchConstitutions();
            console.log('App mounted: Fetched initial constitutions.');

            // Removed logic to auto-select most recent conversation

        } catch (error) {
            console.error("App onMount Error: Failed to fetch initial constitutions:", error);
            // Error display is handled by the globalError store via apiFetch
        }
    });
</script>

<main class="app-layout">
    <div class="app-header">
        <h1 class="app-title">
            <span class="logo-text">Superego</span>
            <span class="subtitle">Demo</span>
        </h1>
        <div class="theme-toggle-container">
            <ThemeToggle />
        </div>
        
    </div>
    <div class="app-content">
        <Sidebar />
        <ChatInterface />
    </div>
</main>

<style>
    /* Styles remain unchanged */
    .app-layout {
        display: flex;
        flex-direction: column;
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

    .app-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 16px;
        background-color: var(--bg-elevated);
        border-bottom: 1px solid var(--input-border);
        height: 50px;
        flex-shrink: 0;
    }

    .app-content {
        display: flex;
        flex: 1;
        overflow: hidden;
    }

    .app-title {
        margin: 0;
        display: flex;
        align-items: center; /* Changed to horizontal alignment */
        font-size: 1em; /* Make the entire title smaller */
    }

    .logo-text {
        background: linear-gradient(135deg, var(--primary-light), var(--secondary));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
        font-size: 1em; /* Reduced from 1.4em */
        font-weight: bold;
    }

    .subtitle {
        margin-left: 8px; /* Add space between Superego and Demo */
        font-size: 0.9em;
        color: var(--text-secondary);
        font-weight: normal;
    }

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

    @media (max-width: 768px) {
        .app-layout {
            flex-direction: column;
        }
    }

    @supports (-webkit-touch-callout: none) {
        .app-layout {
            height: -webkit-fill-available;
        }
    }

    .theme-toggle-container {
        margin-left: auto;
    }

    @media (max-width: 768px) {
        .app-content {
            flex-direction: column;
        }
    }
</style>

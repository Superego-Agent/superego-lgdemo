  <script lang="ts">
  // Removed incorrect $effect import - runes are compiler features
  import { sessionStore } from '$lib/state/session.svelte';
  import { threadStore } from '$lib/state/threads.svelte';
import { onMount } from 'svelte';
import { constitutionStore } from '$lib/state/constitutions.svelte'; // Use updated single store instance
import { sendApiKeyToBackend } from '$lib/services/apiKey.svelte';
import { apiKeyStore, setApiKey } from '$lib/state/apiKey.svelte';
import Sidebar from './lib/components/Sidebar.svelte';
import ChatInterface from '$lib/components/ChatInterface.svelte';
import ThemeToggle from './lib/components/ThemeToggle.svelte';
import './lib/styles/theme.css';
import './lib/styles/dark-theme.css';

// Removed duplicate sessionStore import
onMount( async () => {
    try {
        await Promise.all([
            // constitutionStore.load(), // Removed - store loads itself via $effect.pre

        ]); // End of Promise.all
  // $effect block moved outside onMount below
    } catch (error) {
        console.error("App onMount Error: Failed to initialize constitutions:", error);
    }

    // --- START: Add Session Initialization Logic ---
    const currentActiveId = sessionStore.activeSessionId; 
    if (currentActiveId === null) {
        const currentSessions = sessionStore.uiSessions;
        const sessionIds = Object.keys(currentSessions);
        if (sessionIds.length > 0) {
            // Activate the first existing session found
            sessionStore.setActiveSessionId(sessionIds[0]); 
            console.log(`[App.svelte] Activated existing session: ${sessionIds[0]}`);
        } else {
            // No sessions exist, create a new one
            console.log('[App.svelte] No existing sessions found, creating a new one.');
            sessionStore.createNewSession(); // This function already sets it as active
        }
    }
    // --- END: Add Session Initialization Logic ---

    // Try to send an empty API key to the backend to check status
    try {
        console.log('[App.svelte] Checking API key status...');
        await sendApiKeyToBackend();
        console.log('[App.svelte] API key is set and ready.');
    } catch (error) {
        // This is expected if no API key is set yet
        console.log('[App.svelte] API key needed: ' + (error instanceof Error ? error.message : String(error)));
        // We'll show a message in the UI via the activeStore global error
    }

}); // End of onMount

// Effect to send API key to backend when it changes
$effect(() => {
    const apiKey = $apiKeyStore;
    if (apiKey) {
        console.log('[App.svelte] API key changed, sending to backend...');
        // Make sure the encrypted key is updated
        setApiKey(apiKey);
        sendApiKeyToBackend().catch(error => {
            console.error('[App.svelte] Error sending API key to backend:', error);
        });
    }
});

  // --- Effect to load history for active session threads ---
  // This runs reactively whenever activeSession or threadCacheStore changes

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

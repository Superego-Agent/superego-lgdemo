<script lang="ts">
import { onMount } from 'svelte';
import Sidebar from './lib/components/Sidebar.svelte';
import ChatInterface from './lib/components/ChatInterface.svelte';
import ThemeToggle from './lib/components/ThemeToggle.svelte';
import { theme } from './lib/stores/theme';
import { fetchConstitutions, fetchCurrentUser, logoutUser } from './lib/api'; // Import fetchCurrentUser and logoutUser
import authStore from './lib/stores/authStore'; // Import the auth store
import { loadLocalConstitutions } from './lib/localConstitutions'; // Import the new function
import './lib/styles/theme.css';
import './lib/styles/dark-theme.css';

// --- Logout Handler ---
async function handleLogout() {
    try {
        await logoutUser();
        authStore.clearUser(); // Clear user state in the store
        console.log('User logged out successfully.');
        // Optionally redirect or refresh if needed, but clearing store should update UI
    } catch (error) {
        console.error('Logout failed:', error);
        // Optionally show an error message to the user
    }
}

onMount( async () => {
    // Check authentication status first
    try {
        const user = await fetchCurrentUser();
        if (user) {
            authStore.setUser(user);
            console.log('User authenticated:', user.email);
        } else {
            authStore.clearUser(); // Ensure state is cleared if not authenticated
            console.log('User not authenticated.');
        }
    } catch (error) {
        // Non-401 errors during auth check
        console.error("App onMount Error: Failed to check authentication status:", error);
        authStore.setError('Failed to check login status.'); // Set error state in store
    }

    // Then load constitutions
    try {
        // Load both global and local constitutions
        await Promise.all([
            fetchConstitutions(),
            loadLocalConstitutions() // Call the function here
        ]);
        console.log('Fetched initial global constitutions and loaded local ones.');
    } catch (error) {
        // Handle potential errors from either fetch or load
        console.error("App onMount Error: Failed to initialize constitutions:", error);
    }
});

</script>

<main class="app-layout">
    <div class="app-header">
        <h1 class="app-title">
            <span class="logo-text">Superego</span>
            <span class="subtitle">Demo</span>
        </h1>

        <!-- Auth Section -->
        <div class="auth-section">
            {#if $authStore.isLoading}
                <span>Loading user...</span>
            {:else if $authStore.isAuthenticated && $authStore.user}
                <div class="user-info">
                    {#if $authStore.user.picture}
                        <img src={$authStore.user.picture} alt="User avatar" class="user-avatar" referrerpolicy="no-referrer" />
                    {/if}
                    <span class="user-name">{$authStore.user.name || $authStore.user.email}</span>
                    <button on:click={handleLogout} class="logout-button">Logout</button>
                </div>
            {:else}
                <a href="{authStore.getBackendUrl()}/api/auth/google/login" class="login-button">Login with Google</a>
            {/if}
            {#if $authStore.error}
                 <span class="auth-error">Error: {$authStore.error}</span>
            {/if}
        </div>
        <!-- End Auth Section -->

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

    .auth-section {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-left: auto; /* Push auth section towards the right */
        margin-right: 16px; /* Add some space before theme toggle */
    }

    .user-info {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .user-avatar {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        object-fit: cover;
    }

    .user-name {
        font-size: 0.9em;
        color: var(--text-secondary);
        max-width: 150px; /* Prevent long names/emails from breaking layout */
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .login-button, .logout-button {
        padding: 6px 12px;
        font-size: 0.85em;
        border-radius: var(--radius-sm);
        cursor: pointer;
        text-decoration: none;
        transition: background-color 0.2s, color 0.2s;
        white-space: nowrap;
    }

    .login-button {
        background-color: var(--primary);
        color: white;
        border: none;
    }
    .login-button:hover {
        background-color: var(--primary-light);
    }

    .logout-button {
        background-color: var(--bg-surface);
        color: var(--text-secondary);
        border: 1px solid var(--input-border);
    }
    .logout-button:hover {
        background-color: var(--bg-elevated);
        border-color: var(--text-secondary);
    }

    .auth-error {
        color: var(--error-text);
        font-size: 0.8em;
    }


    .theme-toggle-container {
        /* margin-left: auto; Removed, auth-section now handles this */
    }

    @media (max-width: 768px) {
        .app-content {
            flex-direction: column;
        }
    }
</style>

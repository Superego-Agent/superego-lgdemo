<script lang="ts">
	import Sidebar from './lib/components/Sidebar.svelte';
	import ChatInterface from './lib/components/ChatInterface.svelte';
</script>

<main class="app-layout">
	<Sidebar />
	<ChatInterface />
</main>

<style>
	.app-layout {
		display: flex;
		height: 100vh; /* Full viewport height */
		width: 100vw; /* Full viewport width */
        overflow: hidden; /* Prevent layout issues */
	}

    /* Ensure global styles don't interfere too much */
    :global(body) {
        margin: 0;
        font-family: sans-serif;
        background-color: #f0f0f0; /* Or match sidebar/chat bg */
    }
    :global(*, *::before, *::after) {
        box-sizing: border-box;
    }
</style>
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
		height: 100%;
		width: 100%;
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		overflow: hidden; /* Prevent layout issues */
	}

    /* Ensure global styles don't interfere too much */
    :global(body) {
        margin: 0;
        padding: 0;
        font-family: sans-serif;
        background-color: #f0f0f0; /* Or match sidebar/chat bg */
        overflow: hidden;
        position: fixed;
        width: 100%;
        height: 100%;
        touch-action: manipulation;
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
</style>

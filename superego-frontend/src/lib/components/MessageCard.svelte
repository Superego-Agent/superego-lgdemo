<script lang="ts">
	export let message: MessageType;

    // Reactive properties based on message type
    $: cardClass = `message-card ${message.sender}`;
    $: senderLabel = getSenderLabel(message);
    $: nodeLabel = message.node ? ` | Node: ${message.node}` : '';
    $: setLabel = message.set_id ? `[Set: ${message.set_id}] ` : '';

    function getSenderLabel(msg: MessageType): string {
        switch(msg.sender) {
            case 'human': return 'You';
            case 'ai': return 'AI'; // Could refine with node later
            case 'tool': return 'Tool';
            case 'system': return 'System';
            default: return 'Unknown';
        }
    }

    // Simple check for tool messages with arguments/results to expand
    $: isToolMessage = message.sender === 'tool';
    $: hasToolDetails = isToolMessage && ( (message as ToolCallMessage).tool_args || (message as ToolCallMessage).result );
    let showDetails = false; // State for expanding tool details

</script>

<div class={cardClass}>
	<div class="header">
		<span class="sender-label">{setLabel}{senderLabel}</span>
        {#if message.node}
		    <span class="node-label">{nodeLabel}</span>
        {/if}
        {#if isToolMessage}
             <span class="tool-status">({(message as ToolCallMessage).status})</span>
        {/if}
	</div>
	<div class="content">
        {@html message.content.replace(/\n/g, '<br/>')} </div>

    {#if hasToolDetails}
        <div class="tool-details-toggle" on:click={() => showDetails = !showDetails}>
            {showDetails ? 'Hide' : 'Show'} Details
        </div>
        {#if showDetails}
            <div class="tool-details">
                {#if (message as ToolCallMessage).tool_args}
                    <pre>Args: {JSON.stringify((message as ToolCallMessage).tool_args, null, 2)}</pre>
                {/if}
                {#if (message as ToolCallMessage).result}
                    <pre>Result: {(message as ToolCallMessage).result}</pre>
                {/if}
            </div>
        {/if}
    {/if}

     {#if message.sender === 'system' && message.isError}
        <div class="error-indicator">Error</div>
     {/if}
</div>

<style>
	.message-card {
		padding: 12px 18px;
		border-radius: 8px;
		margin-bottom: 5px; /* Replaced gap in container */
		max-width: 85%;
        word-wrap: break-word;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        position: relative; /* For potential absolute elements later */
	}

	.human {
		background-color: #e1f5fe; /* Light blue */
		align-self: flex-end;
        margin-left: 15%;
	}

	.ai {
		background-color: #e8f5e9; /* Light green */
		align-self: flex-start;
        margin-right: 15%;
	}

	.tool {
		background-color: #fffde7; /* Light yellow */
		align-self: flex-start; /* Or center? Tools are part of AI turn */
        margin-right: 15%;
        border: 1px dashed #ccc;
	}

    .system {
        background-color: #fce4ec; /* Light pink/error */
        align-self: center;
        font-style: italic;
        color: #555;
        border: 1px solid #f8bbd0;
        text-align: center;
        max-width: 100%;
    }

	.header {
		font-size: 0.8em;
		font-weight: bold;
		color: #555;
		margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 5px;
	}
    .sender-label { color: #333; }
	.node-label { font-style: italic; color: #777; }
    .tool-status { font-weight: normal; color: #888; font-size: 0.9em; }

	.content {
		font-size: 1em;
		line-height: 1.5;
        white-space: pre-wrap; /* Preserve line breaks */
	}

    .tool-details-toggle {
        font-size: 0.8em;
        color: blue;
        text-decoration: underline;
        cursor: pointer;
        margin-top: 8px;
    }

    .tool-details {
        margin-top: 5px;
        padding: 8px;
        background-color: rgba(0,0,0,0.03);
        border-radius: 4px;
        font-size: 0.85em;
    }
    .tool-details pre {
        white-space: pre-wrap;
        word-wrap: break-word;
        margin: 0;
        font-family: monospace;
    }
    .error-indicator {
        position: absolute;
        top: 5px;
        right: 10px;
        font-size: 0.7em;
        font-weight: bold;
        color: red;
        background-color: white;
        padding: 1px 4px;
        border-radius: 3px;
    }
</style>
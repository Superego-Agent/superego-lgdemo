<script lang="ts">
	import { fade, fly, scale } from 'svelte/transition';
	import { elasticOut } from 'svelte/easing';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	import ToolIcon from '~icons/fluent/wrench-24-regular'; // Use Fluent wrench icon

	interface Props {
		message: MessageType;
	}

	let { message }: Props = $props();

	// Removed sender variable, use message.type directly
	// Use message.nodeId directly where needed

	// Correctly determine if the message represents an error
	let isError = $derived(message.type === 'tool' && message.is_error === true);
	// Note: SystemApiMessage doesn't have an is_error flag in global.d.ts

	// Get tool name safely
	let toolName = $derived(message.type === 'tool' ? message.name : null);

	// Get AI message safely
	let aiMessage = $derived(message.type === 'ai' ? message : null);


	const titleMap: Record<string, string | undefined> = {
		human: 'You',
		system: 'System',
		// AI and Tool titles are handled dynamically based on nodeId or tool name
	};

	// Map node IDs and message types to accent colors
	const accentColorMap: Record<string, string> = {
		// Node IDs (adjust if backend sends different IDs)
		'input_moderator': 'var(--node-superego)', // Example node ID for superego
		'agent': 'var(--node-inner-agent)', // Example node ID for inner agent
		'action': 'var(--node-tools)', // Example node ID for tool execution node

		// Message Types (Fallbacks)
		human: 'var(--text-primary)', // Use primary text color for 'You' title contrast
		system: 'var(--system-border)',
		ai: 'var(--node-inner-agent)', // Default AI color if no specific node
		tool: 'var(--node-tools)', // Default tool color if no specific node
	};

	// Determine accent color based on error status, node ID, or message type
	let cardAccentColor = $derived(isError
		? 'var(--error)'
		: accentColorMap[message.nodeId] ?? accentColorMap[message.type] ?? 'var(--node-default)');

	// Determine the title displayed on the card
	let title = $derived((() => {
		if (message.type === 'ai') {
			// Use Node ID for AI messages if available, otherwise 'AI'
			return message.nodeId?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) ?? 'AI';
		} else if (message.type === 'tool') {
			// Use tool name for tool messages
			return `Tool: ${toolName ?? 'Result'}`;
		} else if (message.type === 'human' || message.type === 'system') {
			// Use the title map for human/system
			return titleMap[message.type];
		}
		return undefined; // Default case
	})());

	// Generate CSS classes based on message type, node ID, and error status
	let cardClasses = $derived(`message-card ${message.type} ${message.nodeId ? `node-${message.nodeId.toLowerCase().replace(/[^a-z0-9]/g, '-')}` : ''} ${isError ? 'error' : ''}`);


	function getRawContentText(content: MessageType['content']): string {
		if (typeof content === 'string') {
			return content;
		} else if (Array.isArray(content)) {
			return content.map(part => (typeof part === 'object' && part?.type === 'text' ? part.text : String(part))).join('');
		}
		return String(content ?? '');
	}

    // Reverted renderedContent logic to original state (pre-Fix #1)
	let renderedContent = $derived((() => {
		const rawText = getRawContentText(message.content);
		// Simplified logic: directly use rawText for parsing for all types,
		// as the stream processor now sends the correct raw content.
		if (message.type === 'tool') {
			// Use rawText directly. The faulty regex parsing is removed.
			const displayContent = rawText || (isError ? 'Error occurred' : '(No result)');
			// Original try/catch for tool content
			try {
				const html = marked.parse(displayContent, { gfm: true, breaks: true });
				return DOMPurify.sanitize(String(html));
			} catch (e) {
				console.error("Markdown parsing error for tool result:", e);
				// Use literal < and > for fallback pre tag
				return `<pre class="error-content">${displayContent.replace(/</g, '<').replace(/>/g, '>')}</pre>`;
			}
		} else {
			// Original try/catch for other content
			try {
				const html = marked.parse(rawText, { gfm: true, breaks: true });
				return DOMPurify.sanitize(String(html));
			} catch (e) {
				console.error("Markdown parsing error:", e);
				// Use literal < and > for fallback pre tag
				return `<pre class="error-content">${rawText.replace(/</g, '<').replace(/>/g, '>')}</pre>`;
			}
		}
	})());


	function formatToolArgs(args: any): string {
		if (args === null || args === undefined || args === '') {
			return "";
		}

		let formattedArgs = '';
		try {
			const valueToFormat = (typeof args === 'string') ? JSON.parse(args) : args;
			formattedArgs = JSON.stringify(valueToFormat, null, 2);
		} catch (e) {
			formattedArgs = String(args);
		}
		// Use literal < and > for pre tag
		return `<pre class="tool-args-content">${formattedArgs}</pre>`;
	}

	// Animation properties based on message type
	let animProps = $derived((() => {
		const common = { duration: 300, easing: elasticOut };
		const position = message.type === 'human' ? { y: -20, x: 20 } : { y: 20, x: -20 };
		return { ...common, ...position };
	})());

</script>

<div class="message-card-wrapper" in:fly|local={animProps}>
	<div class={cardClasses} style="--card-accent-color: {cardAccentColor}">
		{#if title}
			<div class="message-title" style:color={cardAccentColor}>
		<!-- === Message Title (Type/Node/Tool Name) === -->
				{#if message.type === 'tool'}
					<span class="tool-icon"><ToolIcon /></span>
				{/if}
				<span class="title-text" in:scale|local={{duration: 200, delay: 100, start: 0.8}}>
					{title}
				</span>
			</div>
		{/if}

		<div class="message-content main-content">
			{@html renderedContent}
		<!-- === Main Message Content (Rendered Markdown) === -->
		</div>

		{#if message.type === 'ai' && aiMessage?.tool_calls && aiMessage.tool_calls.length > 0}
			<div class="tool-calls-separator"></div>
		<!-- === AI Tool Calls (If any) === -->
			<div class="tool-calls-section">
				{#each aiMessage.tool_calls as toolCall, i (toolCall.id || toolCall.name)}
					<div class="tool-call-item" in:fade|local={{delay: 100 + i * 50, duration: 200}}>
						<span class="tool-call-prefix">↳ Called {toolCall.name || 'Tool'}:</span>
						{@html formatToolArgs(toolCall.args)}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<style lang="scss">
	@use '../styles/mixins' as *;

	/* CSS rule for human title color removed */

	.message-card-wrapper {
		width: 100%; /* Reverted */
		margin-bottom: var(--space-md);
		padding: 0 var(--space-sm);
	}

	.message-card {
		@include base-card($bg: var(--ai-bg), $radius: var(--radius-lg), $shadow: var(--shadow-md)); /* Reverted shadow */
		padding: var(--space-md);
		max-width: min(60ch, 90%);
		position: relative;
		overflow-wrap: break-word;
		word-break: break-word;
		color: var(--text-primary);
		transition: all 0.2s ease;

		&:hover { /* Literal & */
			box-shadow: var(--shadow-lg);
			transform: translateY(-1px);
		}
	}

	.message-card.human {
		background-color: var(--human-bg);
		margin-left: auto;
		color: var(--text-primary);
	}

	.message-card.ai {
		background-color: var(--ai-bg);
		margin-right: auto;
	}

	.message-card.tool {
		// Slightly different background for tool results
		background-color: color-mix(in srgb, var(--ai-bg) 90%, var(--bg-primary) 10%);
		margin-right: auto;
	}

	.message-card.system {
		background-color: var(--system-bg);
		font-style: italic;
		color: var(--text-primary);
		max-width: 100%;
	}

	.message-card.system.error, .message-card.tool.error {
		background-color: var(--error-bg);
		color: var(--text-primary);
	}

	.message-title {
		font-weight: 600;
		margin: 0 calc(-1 * var(--space-md)) var(--space-sm);
		padding: 0 var(--space-md) var(--space-xs);
		font-size: 0.875rem;
		display: flex;
		align-items: center;
		gap: var(--space-xs); // Add gap for icon
		border-bottom: 1px solid var(--input-border);
		width: calc(100% + 2 * var(--space-md));
	}

	.tool-icon {
		display: inline-flex;
		align-items: center;
		font-size: 1.1em; // Adjust icon size if needed
		opacity: 0.8;
	}

	.title-text {
		display: inline-block;
	}

	.message-content {
		font-size: 1rem;
		line-height: 1.6;
		/* white-space: pre-wrap; */ /* Removed this - might interfere with wrapping of non-pre elements */
	}

	:global(.message-content p) {
		margin-bottom: 0.75em;
	}

	:global(.message-content ul), :global(.message-content ol) {
		margin-left: 1.5em;
		margin-bottom: 0.75em;
	}

	:global(.message-content li) {
		margin-bottom: 0.25em;
	}

	:global(.message-content pre) {
		background-color: var(--bg-elevated);
		padding: 0.75em;
		border-radius: var(--radius-sm);
		overflow-x: auto;
		font-family: 'Fira Code', 'Roboto Mono', monospace;
		font-size: 0.9em;
		margin-bottom: 0.75em;
		color: var(--text-primary);
		white-space: pre;
	}

	:global(.message-content code:not(pre code)) {
		background-color: var(--bg-elevated);
		padding: 0.2em 0.4em;
		border-radius: var(--radius-sm);
		font-size: 0.9em;
		color: var(--secondary-light);
		font-family: 'Fira Code', 'Roboto Mono', monospace;
	}

	:global(.message-content blockquote) {
		border-left: 3px solid var(--input-border);
		padding-left: 1em;
		margin-left: 0;
		margin-right: 0;
		font-style: italic;
		color: var(--text-secondary);
	}

	:global(.message-content table) {
		width: auto;
		border-collapse: collapse;
		margin-bottom: 1em;
	}

	:global(.message-content th), :global(.message-content td) {
		border: 1px solid var(--input-border);
		padding: 0.5em 0.75em;
	}

	:global(.message-content th) {
		background-color: var(--bg-elevated);
	}

	:global(.message-content a) {
		color: var(--secondary-light);
		text-decoration: underline;
		transition: color 0.2s ease;
	}

	:global(.message-content a:hover) {
		color: var(--secondary);
	}

   .tool-calls-separator {
		border-top: 1px dashed var(--input-border);
		margin-top: var(--space-md);
		margin-bottom: var(--space-md);
	}

   .tool-calls-section {
		font-size: 0.875rem;
		color: var(--text-secondary);
	}

   .tool-call-item {
		margin-bottom: var(--space-sm);
	}

   .tool-call-prefix {
		font-style: italic;
		color: var(--text-secondary);
		margin-right: 0.5em;
	}

   .tool-call-args {
		display: block;
		background-color: var(--bg-elevated);
		padding: var(--space-sm);
		border-radius: var(--radius-sm);
		overflow-x: auto;
		font-family: 'Fira Code', 'Roboto Mono', monospace;
		font-size: 0.85em;
		color: var(--text-primary);
		white-space: pre;
		margin: var(--space-xs) 0 0 0;
		padding: 0;
		background: none;
	}

	/* Style for the <pre> tag generated for tool results content - REMOVED as <pre> is no longer used */

	/* Style for the <pre> tag generated for error content */
	.error-content {
		white-space: pre-wrap;
		word-break: break-word;
		font-family: inherit;
		font-size: inherit;
		margin: 0;
		padding: 0;
		background: none;
		color: var(--error);
	}

	/* Style for the <pre> tag generated for tool call arguments */
	:global(.tool-args-content) {
		display: block; /* Ensure it takes block layout */
		background-color: var(--bg-elevated);
		padding: var(--space-sm);
		border-radius: var(--radius-sm);
		overflow-x: scroll; /* Always show scrollbar for horizontal overflow */
		white-space: pre; /* Prevent wrapping */
		font-family: 'Fira Code', 'Roboto Mono', monospace;
		font-size: 0.85em;
		color: var(--text-primary);
		margin-top: var(--space-xs); /* Add some space above */
	}


	.message-set-id {
		font-size: 0.75rem;
		color: var(--text-secondary);
		text-align: right;
		margin-top: var(--space-sm);
	}

</style>

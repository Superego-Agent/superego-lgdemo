<script lang="ts">
	import { fade, fly, scale } from 'svelte/transition';
	import { elasticOut } from 'svelte/easing';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	import ToolIcon from '~icons/fluent/wrench-24-regular'; // Use Fluent wrench icon

	export let message: MessageType;

	$: sender = message.sender;
	$: node = message.node;
	$: isError = (sender === 'system' && (message as SystemMessage).isError) ||
				(sender === 'tool_result' && (message as ToolResultMessage).is_error);
	$: toolName = (sender === 'tool_result') ? (message as ToolResultMessage).tool_name : null;
	$: aiMessage = sender === 'ai' ? (message as AIMessage) : null;
	$: toolResultMsg = sender === 'tool_result' ? (message as ToolResultMessage) : null;

	const titleMap: Record<string, string | undefined> = {
		human: 'You',
		system: 'System'
	};

	const accentColorMap: Record<string, string> = {
		superego: 'var(--node-superego)',
		inner_agent: 'var(--node-inner-agent)',
		tools: 'var(--node-tools)',
		human: 'var(--human-border)',
		system: 'var(--system-border)'
	};

	$: cardAccentColor = isError
		? 'var(--error)'
		: accentColorMap[node ?? ''] ?? accentColorMap[sender] ?? 'var(--node-default)';

	$: title = sender === 'ai'
		? node?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) ?? 'AI'
		: sender === 'tool_result'
		? `Tool: ${toolName ?? 'Result'}`
		: titleMap[sender];

	$: cardClasses = `message-card ${sender} ${node ? `node-${node.toLowerCase().replace(/[^a-z0-9]/g, '-')}` : ''} ${isError ? 'error' : ''}`;


	function getRawContentText(content: MessageType['content']): string {
		if (typeof content === 'string') {
			return content;
		} else if (Array.isArray(content)) {
			return content.map(part => (typeof part === 'object' && part?.type === 'text' ? part.text : String(part))).join('');
		}
		return String(content ?? ''); 
	}

	$: renderedContent = (() => {
		const rawText = getRawContentText(message.content);
		if (sender === 'tool_result') {
			// Reinstate the logic to extract content='...' if possible
			let displayContent = rawText || (isError ? 'Error occurred' : '(No result)');
			const match = rawText.match(/^content='([^']*)'/);
			if (match && match[1]) {
				displayContent = match[1]; // Use extracted content
			} else if (rawText) {
				// Only warn if there was actual text that didn't match
				console.warn("Tool result content did not match expected pattern. Displaying raw:", rawText);
			}
			// Display extracted or raw content safely within <pre>
			return `<pre class="tool-result-content">${displayContent}</pre>`;
		} else {
			// Keep Markdown processing for other message types
			try {
				const html = marked.parse(rawText, { gfm: true, breaks: true });
				return DOMPurify.sanitize(String(html));
			} catch (e) {
				console.error("Markdown parsing error:", e);
				return `<pre class="error-content">${rawText}</pre>`;
			}
		}
	})();


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
		return `<pre class="tool-args-content">${formattedArgs}</pre>`;
	}

	function getMessageAnimation(msgSender: string) {
		const common = { duration: 300, easing: elasticOut };
		const position = msgSender === 'human' ? { y: -20, x: 20 } : { y: 20, x: -20 };
		return { ...common, ...position };
	}

	$: animProps = getMessageAnimation(sender);

</script>

<div class="message-card-wrapper" in:fly|local={animProps}>
	<div class={cardClasses} style="--card-accent-color: {cardAccentColor}">
		{#if title}
			<div class="message-title" style:color={cardAccentColor}>
				{#if sender === 'tool_result'}
					<span class="tool-icon"><ToolIcon /></span>
				{/if}
				<span class="title-text" in:scale|local={{duration: 200, delay: 100, start: 0.8}}>
					{title}
				</span>
			</div>
		{/if}

		<div class="message-content main-content">
			{@html renderedContent}
		</div>

		{#if sender === 'ai' && aiMessage?.tool_calls && aiMessage.tool_calls.length > 0}
			<div class="tool-calls-separator"></div>
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

	.message-card-wrapper {
		width: 100%;
		margin-bottom: var(--space-md);
		padding: 0 var(--space-sm);
	}

	.message-card {
		@include base-card($bg: var(--ai-bg), $radius: var(--radius-lg), $shadow: var(--shadow-md)); // Use mixin
		padding: var(--space-md);
		max-width: min(60ch, 90%);
		position: relative;
		overflow-wrap: break-word;
		word-break: break-word;
		color: var(--text-primary);
		transition: all 0.2s ease;

		&:hover {
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

	.message-card.tool_result {
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

	.message-card.system.error, .message-card.tool_result.error {
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
		white-space: pre-wrap;
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

	/* Style for the <pre> tag generated for tool results content */
	.tool-result-content {
		white-space: pre-wrap;
		word-break: break-word;
		font-family: inherit;
		font-size: inherit;
		margin: 0;
		padding: 0;
		background: none;
		color: inherit;
	}

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


	.message-set-id {
		font-size: 0.75rem;
		color: var(--text-secondary);
		text-align: right;
		margin-top: var(--space-sm);
	}
</style>

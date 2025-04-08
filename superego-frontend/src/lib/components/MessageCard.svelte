<script lang="ts">
	import { fade, fly, scale } from 'svelte/transition';
	import { elasticOut } from 'svelte/easing';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';

	export let message: MessageType;

	$: sender = message.sender;
	$: node = message.node;
	$: isError = (sender === 'system' && (message as SystemMessage).isError) ||
				(sender === 'tool_result' && (message as ToolResultMessage).is_error);
	$: toolName = (sender === 'tool_result') ? (message as ToolResultMessage).tool_name : null;
	$: aiMessage = sender === 'ai' ? (message as AIMessage) : null;
	$: toolResultMsg = sender === 'tool_result' ? (message as ToolResultMessage) : null;

	$: cardClasses = `message-card ${sender} ${node ? `node-${node.toLowerCase().replace(/[^a-z0-9]/g, '-')}` : ''} ${isError ? 'error' : ''}`;

	$: title = (() => {
	    if (sender === 'ai' || sender === 'tool_result') {
	        return node?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
	    }
		if (sender === 'human') return 'You';
		return null;
	})();

	function getRawContentText(content: MessageType['content']): string {
		if (typeof content === 'string') {
			return content;
		} else if (Array.isArray(content)) {
			return content.map(part => (typeof part === 'object' && part?.type === 'text' ? part.text : String(part))).join('');
		}
		return String(content ?? ''); 
	}

	$: renderedContent = (() => {
		if (sender === 'tool_result') {
			const toolContent = String(toolResultMsg?.content ?? (isError ? 'Error occurred' : '(No result)'));
			return DOMPurify.sanitize(toolContent);
		} else {
			const rawText = getRawContentText(message.content);
			try {
				const html = marked.parse(rawText, { gfm: true, breaks: true });
				return DOMPurify.sanitize(String(html));
			} catch (e) {
				console.error("Markdown parsing error:", e);
				return `<pre>${escapeHtml(rawText)}</pre>`;
			}
		}
	})();

	// Basic HTML escaping for safety
	function escapeHtml(unsafe: string): string {
		if (!unsafe) return '';
		const str = String(unsafe);
		return str.replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">");
	}

	function formatToolArgs(args: any): string {
		if (args === null || args === undefined) {
			return "";
		}

		if (typeof args === 'string') {
			try {
				if (args.trim() === "") return "";
				const parsed = JSON.parse(args);
				return JSON.stringify(parsed, null, 2); 
			} catch (e) {
				console.warn("Failed to parse tool args string as JSON, escaping instead:", args);
				return escapeHtml(args);
			}
		} else if (typeof args === 'object') {
			try {
				return JSON.stringify(args, null, 2); 
			} catch (e) {
				console.error("Failed to stringify tool args object:", args, e);
				return escapeHtml(String(args)); 
			}
		} else {
			return escapeHtml(String(args));
		}
	}

	const accentColorMap: Record<string, string> = {
		superego: 'var(--node-superego)',
		inner_agent: 'var(--node-inner-agent)',
		tools: 'var(--node-tools)',
		tool_result: 'var(--node-tools)', // Group tool results with tools
		human: 'var(--human-border)',
		system: 'var(--system-border)'
	};

	$: cardAccentColor = isError
		? 'var(--error)' 
		: accentColorMap[node ?? ''] ?? accentColorMap[sender] ?? 'var(--node-default)'; 

	function getMessageAnimation(msgSender: string) {
		const common = { duration: 300, easing: elasticOut };
		return msgSender === 'human'
			? { ...common, y: -20, x: 20 } 
			: { ...common, y: 20, x: -20 }; 
	}

	$: animProps = getMessageAnimation(sender);
</script>

<div class="message-card-wrapper" in:fly|local={animProps}>
	<div class={cardClasses} style="--card-accent-color: {cardAccentColor}">
		{#if title}
			<div class="message-title" style:color={cardAccentColor}>
				<span class="title-text" in:scale|local={{duration: 200, delay: 100, start: 0.8}}>
					{title}{#if toolName && sender === 'tool_result'} ({toolName}){/if}
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
					   <pre class="tool-call-args">{formatToolArgs(toolCall.args)}</pre>
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

	.message-card.ai, .message-card.tool_result {
		background-color: var(--ai-bg);
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
		border-bottom: 1px solid var(--input-border);
		width: calc(100% + 2 * var(--space-md));
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
		margin-top: var(--space-xs);
	}

	.message-set-id {
		font-size: 0.75rem;
		color: var(--text-secondary);
		text-align: right;
		margin-top: var(--space-sm);
	}
</style>

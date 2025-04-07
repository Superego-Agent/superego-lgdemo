<script lang="ts">
	import { fade, fly, scale } from 'svelte/transition';
	import { elasticOut } from 'svelte/easing';
	import { marked } from 'marked';
	import DOMPurify from 'dompurify';
	// Uses types from global.d.ts

	export let message: MessageType;

   // --- Reactive Computations ---
	$: sender = message.sender;
	$: node = message.node;
	$: isError = (sender === 'system' && (message as SystemMessage).isError) ||
				(sender === 'tool_result' && (message as ToolResultMessage).is_error);
	$: toolName = (sender === 'tool_result') ? (message as ToolResultMessage).tool_name : null;

	// Use standard AIMessage type, access optional tool_calls
	$: aiMessage = sender === 'ai' ? (message as AIMessage) : null;
	$: toolResultMsg = sender === 'tool_result' ? (message as ToolResultMessage) : null;

	$: cardClasses = `message-card ${sender} ${node ? `node-${node.toLowerCase().replace(/[^a-z0-9]/g, '-')}` : ''} ${isError ? 'error' : ''}`;

	$: title = (() => {
	    if (sender === 'ai' || sender === 'tool_result') {
	        return node?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
	    }
	    if (sender === 'human') {
	        return 'You';
	    }
	    return null;
	})();

	$: titlePrefix = (() => {
	    return '';
	})();

	// Main content rendering
	$: renderedContent = (() => {
		let rawContent = '';
		if (sender === 'tool_result' && toolResultMsg) {
		   // For tool results, extract just the content part
		   let content = toolResultMsg.content ?? (isError ? 'Error occurred' : '(No result)');

		   // Format the content string - handle various tool result formats
		   if (content && typeof content === 'string') {
		       // Try to extract content from common formats

		       // Format: <<< Tool Result Tools (superego_decision) content='✅ Superego allowed the prompt.' ...
		       // We want to extract just the value from content='...'
		       const contentMatch = content.match(/content=['"]([^'"]+)['"]/);
		       if (contentMatch && contentMatch[1]) {
		           content = contentMatch[1];
		       }
		       // If we didn't find a content= match but it still has the Tool Result prefix
		       else if (content.includes('Tool Result')) {
		           // Clean up common prefixes
		           content = content
		               .replace(/<<< Tool Result Tools \([^)]+\)\s*/g, '')
		               .replace(/<<< Tool Result\s*/g, '')
		               .trim();
		       }
		   }

		   return DOMPurify.sanitize(String(content)); // Sanitize the extracted content
		} else if (typeof message.content === 'string') {
		   rawContent = message.content; // Main text content for AI/Human/System
	   } else if (Array.isArray(message.content)) {
		   rawContent = message.content.map(part => (typeof part === 'object' && part?.type === 'text' ? part.text : String(part))).join('');
	   } else {
			rawContent = String(message.content ?? '');
		}
		// Render Markdown and sanitize for AI/Human/System main content
		try {
			// Use escapeHtml from this component scope
			const html = marked.parse(rawContent, { gfm: true, breaks: true });
			return DOMPurify.sanitize(String(html));
		} catch (e) { console.error("Markdown parsing error:", e); return `<pre>${escapeHtml(rawContent)}</pre>`; }
	})();

	// HTML Escaping helper (needed for fallback)
	function escapeHtml(unsafe: string): string {
		if (!unsafe) return '';
		// Ensure input is a string before calling replace
		const str = String(unsafe);
		return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	}

	// Tool call arguments formatting (handles string JSON or already parsed objects)
	function formatToolArgs(args: any): string {
		if (args === null || args === undefined) {
			return ""; // Handle null/undefined explicitly
		}

		if (typeof args === 'string') {
			// If it's a string, try to parse it as JSON
			try {
				if (args.trim() === "") return ""; // Handle empty string
				const parsed = JSON.parse(args);
				// Successfully parsed, now stringify prettily
				return JSON.stringify(parsed, null, 2);
			} catch (e) {
				// Parsing failed, assume it's just a plain string that needs escaping
				console.warn("Failed to parse tool args string as JSON, escaping instead:", args);
				return escapeHtml(args); // Use escapeHtml from this component
			}
		} else if (typeof args === 'object') {
			// If it's already an object (or array), stringify it prettily
			try {
				return JSON.stringify(args, null, 2);
			} catch (e) {
				// Should be rare, but handle potential circular references etc.
				console.error("Failed to stringify tool args object:", args, e);
				return escapeHtml(String(args)); // Fallback to string conversion and escaping
			}
		} else {
			// Handle other types (boolean, number) by converting to string and escaping
			return escapeHtml(String(args)); // Use escapeHtml from this component
		}
	}

	// Card style and accent colors
	$: cardAccentColor = (() => {
		if (isError) return 'var(--error)';
		if (node === 'superego') return 'var(--node-superego)';
		if (node === 'inner_agent') return 'var(--node-inner-agent)';
		if (node === 'tools' || sender === 'tool_result') return 'var(--node-tools)';
		if (sender === 'human') return 'var(--human-border)';
		if (sender === 'system') return 'var(--system-border)';
		return 'var(--node-default)';
	})();

	// Reactive style for title color
	$: finalTitleColor = cardAccentColor;

	// Entry animation setup
	function getMessageAnimation(msgSender: string) {
		if (msgSender === 'human') {
			return {
				y: -20,
				x: 20,
				duration: 300,
				easing: elasticOut
			};
		} else {
			return {
				y: 20,
				x: -20,
				duration: 300,
				easing: elasticOut
			};
		}
	}

	$: animProps = getMessageAnimation(sender);
</script>

<div class="message-card-wrapper" in:fly|local={animProps}>
	<div class={cardClasses} style="--card-accent-color: {cardAccentColor}">
		{#if title}
			<div class="message-title" style:color={finalTitleColor}>
				<span class="title-text" in:scale|local={{duration: 200, delay: 100, start: 0.8}}>
					{titlePrefix} {title} {#if toolName && sender === 'tool_result'}({toolName}){/if}
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

	   {#if message.set_id}
			<div class="message-set-id">Set: {message.set_id}</div>
		{/if}
	</div>
</div>

<style>
	.message-card-wrapper {
		width: 100%;
		margin-bottom: var(--space-md);
		padding: 0 var(--space-sm);
	}

	.message-card {
		border-radius: var(--radius-lg);
		padding: var(--space-md);
		background-color: var(--ai-bg);
		border: 1px solid var(--input-border);
		max-width: min(60ch, 90%); /* Limit width to 60ch or 90%, whichever is smaller */
		position: relative;
		overflow-wrap: break-word;
		word-break: break-word;
		color: var(--text-primary);
		box-shadow: var(--shadow-md);
		transition: all 0.2s ease;
	}

	.message-card:hover {
		box-shadow: var(--shadow-lg);
		transform: translateY(-1px);
	}

	.message-card.human {
		background-color: var(--human-bg);
		margin-left: auto;
		color: var(--text-primary);
		/* Width remains flexible but capped at 60ch */
	}

	.message-card.ai, .message-card.tool_result {
		background-color: var(--ai-bg);
		margin-right: auto;
		/* Width remains flexible but capped at 60ch */
	}

	.message-card.system {
		background-color: var(--system-bg);
		font-style: italic;
		color: var(--text-primary);
		max-width: 100%; /* System messages can still be full width */
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

   /* Styles for appended tool calls section */
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

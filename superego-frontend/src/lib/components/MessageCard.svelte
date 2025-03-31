<script lang="ts">
	import { fade } from 'svelte/transition';
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

	$: title = (sender === 'ai' || sender === 'tool_result') ? node?.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : null;
	$: titlePrefix = sender === 'tool_result' ? '<<< Tool Result' : '>>>';

	// Main content rendering
	$: renderedContent = (() => {
		let rawContent = '';
		if (sender === 'tool_result' && toolResultMsg) {
		   rawContent = toolResultMsg.content ?? (isError ? 'Error occurred' : '(No result)');
			return DOMPurify.sanitize(String(rawContent)); // Sanitize plain text result
		} else if (typeof message.content === 'string') {
		   rawContent = message.content; // Main text content for AI/Human/System
	   } else if (Array.isArray(message.content)) {
		   rawContent = message.content.map(part => (typeof part === 'object' && part?.type === 'text' ? part.text : String(part))).join('');
	   } else {
			rawContent = String(message.content ?? '');
		}
		// Render Markdown and sanitize for AI/Human/System main content
		try {
			const html = marked.parse(rawContent, { gfm: true, breaks: true });
			return DOMPurify.sanitize(String(html));
		} catch (e) { console.error("Markdown parsing error:", e); return `<pre>${escapeHtml(rawContent)}</pre>`; }
	})();

	// Tool call arguments formatting (attempt to parse JSON)
	function formatToolArgs(args: string | undefined | null): string {
		// *** CORRECTED LOGIC ***
		try {
			// Only try to parse if args is a non-empty string after trimming
			if (args && args.trim()) {
				const parsed = JSON.parse(args); // Try parsing the assembled string
				return JSON.stringify(parsed, null, 2); // Pretty print if successful
			} else {
				// If args is null, undefined, empty or whitespace only, treat as parse failure
				throw new Error("Args are effectively empty");
			}
		} catch (e) {
			// If parsing fails (empty, null, undefined, incomplete, malformed JSON),
			// show the raw escaped string accumulated so far.
			return escapeHtml(args || ""); // Show empty string if args was null/undefined
		}
	}

	// HTML Escaping helper
	function escapeHtml(unsafe: string): string { if (!unsafe) return ''; return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

	// Node colors definition
	const nodeColors: Record<string, string> = { default: '#64748b', superego: '#ec4899', inner_agent: '#22c55e', tools: '#f97316', };

	// Reactive style for border color
	$: finalBorderStyle = (() => { let color = nodeColors.default; if (isError) return 'border-color: #ef4444;'; if (node && nodeColors[node]) { color = nodeColors[node]; } else if (sender === 'human') { color = 'transparent'; } else if (sender === 'system') { color = '#eab308'; } else if (sender === 'tool_result') { color = nodeColors['tools'] || nodeColors.default; } return `border-color: ${color};`; })();

	// Reactive style for title color
	$: finalTitleColor = isError && sender !== 'tool_result' ? '#fecaca' : nodeColors[node || 'default'] ?? nodeColors.default;

</script>

<div class="message-card-wrapper" transition:fade|local={{ duration: 200 }}>
	<div class={cardClasses} style={finalBorderStyle}>
		{#if title}
			<div class="message-title" style:color={finalTitleColor}>
				{titlePrefix} {title} {#if toolName && sender === 'tool_result'}({toolName}){/if}
			</div>
		{/if}

	   <div class="message-content main-content">
			{@html renderedContent}
		</div>

	   {#if sender === 'ai' && aiMessage?.tool_calls && aiMessage.tool_calls.length > 0}
		   <div class="tool-calls-separator"></div>
		   <div class="tool-calls-section">
			   {#each aiMessage.tool_calls as toolCall (toolCall.id || toolCall.name)}
				   <div class="tool-call-item">
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
	/* Styles remain the same as the previous structured tool call version */
	.message-card-wrapper { width: 100%; margin-bottom: 0.75rem; padding: 0 0.5rem; }
	.message-card { border-radius: 0.5rem; padding: 0.75rem 1rem; background-color: var(--card-bg-color, #374151); border: 2px solid; max-width: 90%; position: relative; overflow-wrap: break-word; word-break: break-word; color: var(--content-text-color, #f3f4f6); }
	.message-card.human { background-color: var(--human-bg-color, #1e40af); margin-left: auto; border-color: transparent; color: var(--human-text-color, #e5e7eb); }
	.message-card.ai, .message-card.tool_result { background-color: var(--ai-bg-color, #4b5563); margin-right: auto; }
	.message-card.system { background-color: var(--system-bg-color, #451a03); border-color: #eab308; font-style: italic; color: var(--system-text-color, #fef3c7); max-width: 100%; }
	.message-card.system.error, .message-card.tool_result.error { background-color: var(--error-bg-color, #7f1d1d); border-color: #ef4444; color: var(--error-text-color, #fecaca); }
	.message-title { font-weight: 600; margin-bottom: 0.5rem; font-size: 0.875rem; }
	.message-content { font-size: 1rem; line-height: 1.6; white-space: pre-wrap; }
	:global(.message-content p) { margin-bottom: 0.75em; } :global(.message-content ul), :global(.message-content ol) { margin-left: 1.5em; margin-bottom: 0.75em; } :global(.message-content li) { margin-bottom: 0.25em; } :global(.message-content pre) { background-color: #1f2937; padding: 0.75em; border-radius: 0.375rem; overflow-x: auto; font-family: monospace; font-size: 0.9em; margin-bottom: 0.75em; color: #d1d5db; white-space: pre; } :global(.message-content code:not(pre code)) { background-color: #1f2937; padding: 0.2em 0.4em; border-radius: 0.25rem; font-size: 0.9em; color: #e5e7eb; } :global(.message-content blockquote) { border-left: 3px solid #6b7280; padding-left: 1em; margin-left: 0; margin-right: 0; font-style: italic; color: #9ca3af; } :global(.message-content table) { width: auto; border-collapse: collapse; margin-bottom: 1em; } :global(.message-content th), :global(.message-content td) { border: 1px solid #4b5563; padding: 0.5em 0.75em; } :global(.message-content th) { background-color: #374151; } :global(.message-content a) { color: #60a5fa; text-decoration: underline; } :global(.message-content a:hover) { color: #93c5fd; }
   /* Styles for appended tool calls section */
   .tool-calls-separator { border-top: 1px dashed #6b7280; margin-top: 0.75rem; margin-bottom: 0.75rem; }
   .tool-calls-section { font-size: 0.875rem; color: #d1d5db; }
   .tool-call-item { margin-bottom: 0.5rem; }
   .tool-call-prefix { font-style: italic; color: #9ca3af; margin-right: 0.5em; }
   .tool-call-args { display: block; background-color: #1f2937; padding: 0.5em 0.75em; border-radius: 0.375rem; overflow-x: auto; font-family: monospace; font-size: 0.85em; color: #d1d5db; white-space: pre; margin-top: 0.25rem; }
	.message-set-id { font-size: 0.75rem; color: #9ca3af; text-align: right; margin-top: 0.5rem; }
</style>


// Types are globally available from src/global.d.ts

/**
 * Mutates the entry by appending text content from a 'chunk' event.
 * Creates a new AI message if the node changes.
 */
export function handleChunk(entryToMutate: HistoryEntry, chunkData: SSEChunkData): void {
    const messages = entryToMutate.values.messages;

    // Create new AI message if node changes or message list is empty
    if (messages.at(-1)?.nodeId !== chunkData.node) {
        messages.push({
            type: 'ai',
            content: '',
            nodeId: chunkData.node,
            tool_calls: [] // Initialize tool_calls for potential subsequent tool chunks
        });
    }

    const lastMessage = messages.at(-1);
    // Append content if last message is AI and from the same node
    if (lastMessage && lastMessage.type === 'ai') {
         if (typeof lastMessage.content !== 'string') {
            console.warn("Appending chunk to non-string AI content, converting existing content.");
            lastMessage.content = String(lastMessage.content);
         }
         lastMessage.content += chunkData.content;
    // Handle unexpected case: chunk received after non-AI message from same node
    } else if (lastMessage) {
         messages.push({
            type: 'ai',
            content: chunkData.content,
            nodeId: chunkData.node,
            tool_calls: []
        });
        console.warn("Received chunk after non-AI message from same node. Creating new AI message.");
    }
}

/**
 * Mutates the entry by adding/updating tool call info from an 'ai_tool_chunk' event.
 * Creates a new AI message if the node changes.
 */
export function handleToolChunk(entryToMutate: HistoryEntry, toolChunkData: SSEToolCallChunkData): void {
    const messages = entryToMutate.values.messages;
    let lastMessage = messages.at(-1);

    // Create new AI message if node changes or message list is empty
    if (!lastMessage || lastMessage.nodeId !== toolChunkData.node) {
        const newAiMessage: AiApiMessage = {
            type: 'ai',
            content: '',
            nodeId: toolChunkData.node,
            tool_calls: []
        };
        messages.push(newAiMessage);
        lastMessage = newAiMessage;
    // Handle unexpected case: tool chunk received after non-AI message from same node
    } else if (lastMessage.type !== 'ai') {
         const newAiMessage: AiApiMessage = {
            type: 'ai',
            content: '',
            nodeId: toolChunkData.node,
            tool_calls: []
        };
        messages.push(newAiMessage);
        lastMessage = newAiMessage;
        console.warn("Received ai_tool_chunk after non-AI message from same node. Creating new AI message.");
    }

    if (!lastMessage.tool_calls) {
        lastMessage.tool_calls = [];
    }

    // If 'id' is present, start a new tool call structure
    if (toolChunkData.id) {
        lastMessage.tool_calls.push({
            id: toolChunkData.id,
            name: toolChunkData.name || '',
            args: toolChunkData.args || ''
        });
    } else if (toolChunkData.args && lastMessage.tool_calls.length > 0) {
        // If only 'args' are present, append to the *last* tool call's args
        // If only args are present, append to the args of the *last* tool call in the array
        const lastToolCall = lastMessage.tool_calls.at(-1);
        if (lastToolCall) {
            lastToolCall.args += toolChunkData.args;
        } else {
             console.error("Received tool chunk args, but no existing tool call structure found on the message.", lastMessage);
        }
    }
     // Ignore chunks with neither id nor args for now.
     // Ignore chunks with neither id nor args? Or log warning? For now, ignore.
}

/**
 * Mutates the entry by adding a ToolApiMessage based on a 'tool_result' event.
 */
export function handleToolResult(entryToMutate: HistoryEntry, toolResultData: SSEToolResultData): void {
    // Construct the ToolApiMessage directly from the SSE event data fields.
    // Assumes toolResultData contains the necessary fields like content, tool_name, tool_call_id, node, is_error.
    // We no longer use the faulty parseToolResultString utility.
   
    const newToolMessage: ToolApiMessage = {
    	type: 'tool',
    	content: toolResultData.content ?? '',
    	tool_call_id: String(toolResultData.tool_call_id ?? ''),
    	name: toolResultData.tool_name,
    	nodeId: toolResultData.node,
    	is_error: toolResultData.is_error
    };
   
    entryToMutate.values.messages.push(newToolMessage);
}
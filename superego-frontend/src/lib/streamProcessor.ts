// src/lib/streamProcessor.ts
// Contains functions to mutate a HistoryEntry based on SSE events.
// Assumes the input entryToMutate is a deep clone made by the caller (api.ts).

import { parseToolResultString } from './utils';

// Types are globally available from src/global.d.ts

/**
 * Mutates the entry by appending text content from a 'chunk' event.
 * Creates a new AI message if the node changes.
 * Expects chunkData to be of type SSEChunkData (containing node and content).
 */
export function handleChunk(entryToMutate: HistoryEntry, chunkData: SSEChunkData): void {
    const messages = entryToMutate.values.messages;

    // If message list is empty or last message's node is different, create new AI message
    if (messages.at(-1)?.nodeId !== chunkData.node) {
        messages.push({
            type: 'ai',
            content: '', // Start with empty content
            nodeId: chunkData.node, // Use node from the data payload
            tool_calls: [] // Initialize tool_calls for potential subsequent tool chunks
        });
    }

    // Append chunk data to the content of the last message
    // Ensure the last message is treated as an AI message for content appending
    const lastMessage = messages.at(-1);
    if (lastMessage && lastMessage.type === 'ai') {
         // Handle potential non-string content if necessary, though chunks should be strings
         if (typeof lastMessage.content !== 'string') {
            // This case might indicate an unexpected state, convert to string or handle appropriately
            console.warn("Appending chunk to non-string AI content, converting existing content.");
            lastMessage.content = String(lastMessage.content);
         }
         lastMessage.content += chunkData.content; // Use content from the data payload
    } else if (lastMessage) {
        // If the last message isn't AI (e.g., Tool message), but node ID matched,
        // this might be an unexpected sequence. Log or decide handling.
        // For now, we might still append, assuming it's text following a tool result from the same node.
        // Or, more strictly, create a new AI message here too. Let's be strict:
         messages.push({
            type: 'ai',
            content: chunkData.content, // Use content from the data payload
            nodeId: chunkData.node, // Use node from the data payload
            tool_calls: []
        });
        console.warn("Received chunk after non-AI message from same node. Creating new AI message.");
    }
    // If messages was empty, the first 'if' block already created the message and added the chunk.
}

/**
 * Mutates the entry by adding/updating tool call info from an 'ai_tool_chunk' event.
 * Creates a new AI message if the node changes.
 * Expects toolChunkData to be of type SSEToolCallChunkData (containing node, id, name, args).
 */
export function handleToolChunk(entryToMutate: HistoryEntry, toolChunkData: SSEToolCallChunkData): void {
    const messages = entryToMutate.values.messages;
    let lastMessage = messages.at(-1);

    // If message list is empty or last message's node is different, create new AI message
    if (!lastMessage || lastMessage.nodeId !== toolChunkData.node) {
        const newAiMessage: AiApiMessage = {
            type: 'ai',
            content: '', // Start with empty content
            nodeId: toolChunkData.node, // Use node from the data payload
            tool_calls: [] // Initialize tool_calls array
        };
        messages.push(newAiMessage);
        lastMessage = newAiMessage; // Update reference to the newly added message
    } else if (lastMessage.type !== 'ai') {
         // If the last message isn't AI type, create a new one for the tool call
         const newAiMessage: AiApiMessage = {
            type: 'ai',
            content: '',
            nodeId: toolChunkData.node, // Use node from the data payload
            tool_calls: []
        };
        messages.push(newAiMessage);
        lastMessage = newAiMessage;
        console.warn("Received ai_tool_chunk after non-AI message from same node. Creating new AI message.");
    }

    // Ensure tool_calls array exists on the target AI message
    if (!lastMessage.tool_calls) {
        lastMessage.tool_calls = [];
    }

    // If id is present, it's the start of a new tool call structure
    if (toolChunkData.id) {
        lastMessage.tool_calls.push({
            id: toolChunkData.id,
            name: toolChunkData.name || '', // Use name if provided, else empty
            args: toolChunkData.args || '' // Use args if provided, else empty
        });
    } else if (toolChunkData.args && lastMessage.tool_calls.length > 0) {
        // If only args are present, append to the args of the *last* tool call in the array
        const lastToolCall = lastMessage.tool_calls.at(-1);
        if (lastToolCall) {
            lastToolCall.args += toolChunkData.args;
        } else {
             console.error("Received tool chunk args, but no existing tool call structure found on the message.", lastMessage);
        }
    }
     // Ignore chunks with neither id nor args? Or log warning? For now, ignore.
}

/**
 * Mutates the entry by adding a ToolApiMessage based on a 'tool_result' event.
 * Uses parseToolResultString helper from utils.
 * Expects toolResultData to be of type SSEToolResultData (containing node, tool_name, content, etc.).
 */
export function handleToolResult(entryToMutate: HistoryEntry, toolResultData: SSEToolResultData): void {
    // Parse the result string to extract content, name, and tool_call_id
    const parsedResult = parseToolResultString(toolResultData.content); // Use 'content' field now

    const newToolMessage: ToolApiMessage = {
        type: 'tool',
        content: parsedResult.content ?? '', // Use extracted content
        tool_call_id: parsedResult.tool_call_id ?? '', // Use extracted ID, ensure string type
        name: parsedResult.name ?? toolResultData.tool_name, // Prefer parsed name, fallback to event tool_name
        nodeId: toolResultData.node, // Use node from the data payload
        is_error: toolResultData.is_error
    };

    entryToMutate.values.messages.push(newToolMessage);
}
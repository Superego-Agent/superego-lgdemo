// src/global.d.ts

declare global {
/** Represents a single constitution available for selection. */
interface ConstitutionItem {
    id: string; // e.g., 'kantian_deontological'
    name: string; // e.g., 'Kantian Deontological'
    description?: string; // Optional description
    // content?: string; // Full content likely not needed in frontend list
}

/** Represents a chat thread in the list. */
interface ThreadItem {
    thread_id: string;
    // Add other potential fields like title, last_updated, etc. if the API provides them
    title?: string; // Example: A short title or first message snippet
    updated_at?: string; // Example: ISO timestamp
}

/** Base structure for messages in history or live chat */
interface BaseMessage {
    id: string; // Unique ID for the message/event sequence
    sender: 'human' | 'ai' | 'tool' | 'system';
    content: string; // Primary text content
    node?: string | null; // LangGraph node origin for AI/tool messages
    set_id?: string | null; // For compare mode tracking
    timestamp: number; // To ensure ordering
}

/** Specific structure for AI message chunks (potentially merged) */
interface AIMessage extends BaseMessage {
    sender: 'ai';
}

/** Specific structure for Human messages */
interface HumanMessage extends BaseMessage {
    sender: 'human';
}

/** Specific structure for System/Error messages */
interface SystemMessage extends BaseMessage {
    sender: 'system';
    isError?: boolean;
}

/** Specific structure for Tool Call messages */
interface ToolCallMessage extends BaseMessage {
    sender: 'tool';
    content: string; // e.g., "Calling tool: tool_name"
    tool_name: string;
    tool_args?: any; // Arguments passed to the tool
    status: 'started' | 'pending' | 'completed' | 'error'; // Track status
    result?: string | null; // Result when completed/error
    is_error?: boolean; // If the tool execution resulted in an error
}

/** Represents a message in the frontend chat display. */
type MessageType = HumanMessage | AIMessage | ToolCallMessage | SystemMessage;


/** Structure for the response of fetching thread history. */
interface HistoryResponse {
    thread_id: string;
    messages: MessageType[]; // Array of past messages
}

/** Structure for the response of creating a new thread. */
interface NewThreadResponse {
    thread_id: string;
}

/** Structure matches the backend SSEEventData Pydantic model [cite: 1] */
interface SSEEventData {
    type: "chunk" | "tool_call" | "tool_result" | "error" | "end";
    node?: string | null; // Node where event originated
    data: any; // Specific data depends on the event type
    set_id?: string | null; // For compare mode tracking
}

// --- Data structures within SSEEventData.data ---
interface SSEChunkData {
    // For type="chunk", data is just: string (text chunk)
}
interface SSEToolCallData {
    // For type="tool_call" [cite: 1]
    name: string;
    args: any; // Simplified in backend example [cite: 1]
}
interface SSEToolResultData {
    // For type="tool_result" [cite: 1]
    tool_name: string;
    result: string;
    is_error: boolean;
}
interface SSEEndData {
    // For type="end" [cite: 1]
    thread_id: string;
}
interface SSEErrorData {
    // For type="error", data is just: string (error message) [cite: 1]
}

/** Represents a set of constitutions for comparison mode. */
interface CompareSet {
    id: string; // Unique ID for this set (e.g., 'set1', 'set2')
    constitution_ids: string[]; // List of selected constitution IDs
    // Optional: Add a name field if users can name sets
    name?: string;
}

/** Represents the different operational modes of the UI. */
type AppMode = 'chat' | 'use' | 'compare';


}

// Ensures this file is treated as a module.
export { };
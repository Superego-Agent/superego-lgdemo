// src/global.d.ts

// Make interfaces available globally
declare global {
    /** Represents a single constitution available for selection. */
    interface ConstitutionItem {
        id: string;
        name: string;
        description?: string;
    }

    /** Represents a chat thread (user-facing conversation) in the list. */
    // TODO: This interface might be obsolete now that conversationManager.ts handles metadata.
    // If kept, thread_id should align with backend expectations (likely string UUID).
    interface ThreadItem {
        thread_id: string; // Assuming backend uses string UUIDs now
        name: string;
        last_updated?: string | Date;
    }

    /** Base structure for messages displayed in the UI */
    interface BaseMessage {
        id: string; // Unique ID for the message/event sequence
        sender: 'human' | 'ai' | 'tool_result' | 'system';
        content: string | Array<{type: string, text?: string}> | any; // Flexible content
        node?: string | null; // Originating node in the graph
        set_id?: string | null; // ID for compare mode sets
        timestamp: number; // Unix timestamp (ms)
    }

    /** Tool call structure potentially stored within AIMessage for display */
    interface ToolCall {
        id: string; // May be temporary during streaming if backend doesn't send early
        name: string;
        args: string; // Accumulated arguments string (likely JSON eventually)
    }

    /** AI message - potentially includes structured tool_calls */
    interface AIMessage extends BaseMessage {
        sender: 'ai';
        tool_calls?: ToolCall[]; // Optional array for structured tool calls
    }

    /** Human messages */
    interface HumanMessage extends BaseMessage {
        sender: 'human';
    }

    /** System/Error messages */
    interface SystemMessage extends BaseMessage {
        sender: 'system';
        isError?: boolean;
    }

    /** Tool Result messages */
    interface ToolResultMessage extends BaseMessage {
        sender: 'tool_result';
        content: string; // Result content (usually stringified JSON or text)
        tool_name: string;
        is_error: boolean;
        tool_call_id?: string | null; // Optional ID linking back to the initiating tool call
    }

    /** Represents any message type in the frontend chat display. */
    type MessageType = HumanMessage | AIMessage | ToolResultMessage | SystemMessage;


    // --- API Response/Request Types ---

    /** Response when fetching history for a thread. */
    interface HistoryResponse {
        messages: MessageType[];
        thread_id: string; // Changed to string (UUID)
        thread_name?: string; // The user-defined name of the thread
    }

    // NewThreadResponse is removed

    /** Input structure for starting a run */
    interface StreamRunInput {
        type: "human";
        content: string;
    }

    /** Request body for starting a normal streaming run. */
    interface StreamRunRequest {
        thread_id: string | null; // Changed to string | null (UUID)
        input: StreamRunInput;
        constitution_ids?: string[];
    }

    /** Defines a set of constitutions for comparison. */
    interface CompareSet {
        id: string; // User-defined ID for the set (e.g., 'strict_vs_default')
        constitution_ids: string[];
        // name?: string; // Optional name, not used by backend currently
    }

    /** Request body for starting a comparison streaming run. */
    interface CompareRunRequest {
        thread_id: string | null; // Changed to string | null (UUID)
        input: StreamRunInput;
        constitution_sets: CompareSet[];
    }


    // --- Server-Sent Event (SSE) Data Types ---

    /** Structure for tool call fragments streamed from the AI */
    interface SSEToolCallChunkData {
        id?: string | null; // Tool call ID, crucial for matching
        name?: string | null; // Tool name fragment
        args?: string | null; // Argument JSON string fragment
    }

    /** Structure for completed tool results */
    interface SSEToolResultData {
        tool_name: string;
        result: string; // Stringified result
        is_error: boolean;
        tool_call_id?: string | null; // ID of the tool call that generated this
    }

    /** Structure for the final 'end' event payload */
    interface SSEEndData {
        thread_id: string; // Changed to string (UUID)
    }

    /** Overall structure of data received via SSE */
    interface SSEEventData {
        type: "chunk" | "ai_tool_chunk" | "tool_result" | "error" | "end";
        node?: string | null; // Graph node where event originated
        // Type of data depends on the 'type' field
        data: string | SSEToolCallChunkData | SSEToolResultData | SSEEndData | any; // Allow flexibility for 'chunk' (string) or 'error' (any)
        set_id?: string | null; // Identifier for compare mode sets
    }

    // --- Application State/Mode Types ---
    type AppMode = 'chat' | 'use' | 'compare'; // Still relevant if UI uses modes? Sidebar removed it.

}

// Ensures this file is treated as a module. Required for declare global.
export { };

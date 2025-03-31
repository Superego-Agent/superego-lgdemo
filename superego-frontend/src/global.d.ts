// src/global.d.ts

declare global {
    /** Represents a single constitution available for selection. */
    interface ConstitutionItem { id: string; name: string; description?: string; }
    /** Represents a chat thread in the list. */
    interface ThreadItem { thread_id: string; title?: string; updated_at?: string; }

    /** Base structure for messages */
    interface BaseMessage {
        id: string; // Unique ID for the message/event sequence
        sender: 'human' | 'ai' | 'tool_result' | 'system';
        content: string | Array<{type: string, text?: string}> | any; // Should primarily resolve to string for AI/Human display
        node?: string | null;
        set_id?: string | null;
        timestamp: number;
    }

    /** Tool call structure stored within AIMessage */
    interface ToolCall {
        // id might be temporary during streaming if not sent initially
        id: string;
        name: string;
        // args accumulate as string fragments until valid JSON is formed (or stream ends)
        args: string;
    }

    /** AI message - Includes optional structured tool_calls */
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
        content: string; // Result content
        tool_name: string;
        is_error: boolean;
        // Corresponds to the tool call that produced this result - ID might be useful if available
        tool_call_id?: string | null;
    }

    /** Represents a message in the frontend chat display. */
    type MessageType = HumanMessage | AIMessage | ToolResultMessage | SystemMessage;


    // --- Other interfaces ---
    interface HistoryResponse { thread_id: string; messages: MessageType[]; }
    interface NewThreadResponse { thread_id: string; }
    interface SSEEventData { type: "chunk" | "ai_tool_chunk" | "tool_result" | "error" | "end"; node?: string | null; data: any; set_id?: string | null; }
    interface SSEToolCallChunkData { id?: string | null; name?: string | null; args?: string | null; } // Ensure ID is sent from backend
    interface SSEToolResultData { tool_name: string; result: string; is_error: boolean; tool_call_id?: string | null; } // Add optional tool_call_id
    interface SSEEndData { thread_id: string; }
    interface CompareSet { id: string; constitution_ids: string[]; name?: string; }
    type AppMode = 'chat' | 'use' | 'compare';
    interface StreamRunInput { type: "human"; content: string; }
    interface StreamRunRequest { thread_id?: string | null; input?: StreamRunInput; constitution_ids?: string[]; }
    // CompareRunSet defined above
    interface CompareRunRequest { input: StreamRunInput; constitution_sets: CompareSet[]; }

}
export { }; // Ensures this file is treated as a module.
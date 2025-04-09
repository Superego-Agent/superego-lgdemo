// src/global.d.ts

// Make interfaces available globally
declare global {
    /** Represents a single constitution available for selection. */
    interface ConstitutionItem {
        id: string;
        title: string; // Changed from name to title
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

    /** Represents a constitution stored locally in localStorage */
    interface LocalConstitution {
        id: string; // Unique local ID (e.g., UUID)
        title: string;
        text: string;
        createdAt: string; // ISO timestamp string
        // Add lastUpdatedAt?
    }

    // --- API Request/Response Types ---

    /**
     * Represents a constitution selected by its ID (typically global/predefined)
     * for sending to the backend in the streamRun request.
     * Includes the user-specified adherence level and title.
     */
    interface BackendConstitutionRefById {
        id: string;
        title: string; // Title is needed for the backend report
        adherence_level: number; // 1-5, now required
    }

    /**
     * Represents a local constitution provided with its full text
     * for sending to the backend in the streamRun request.
     * Includes the user-specified adherence level and title.
     */
    interface BackendConstitutionFullText {
        // id is not strictly needed by the backend here, but title is
        title: string;
        text: string;
        adherence_level: number; // 1-5, now required
    }

    /**
     * Union type for constitutions sent to the backend in the streamRun request.
     */
    type SelectedConstitution = BackendConstitutionRefById | BackendConstitutionFullText;


    // --- Old types, commented out for reference, replaced by BackendConstitution... types for streamRun ---
    // /** API request structure for referencing a constitution by ID */
    // interface ConstitutionRefById {
    //     id: string;
    //     adherence_level?: number; // Optional adherence level (1-5)
    // }
    //
    // /** API request structure for referencing a constitution by its text content */
    // interface ConstitutionRefByText {
    //     text: string;
    //     adherence_level?: number; // Optional adherence level (1-5)
    // }

    /** Input structure for starting a run */
    interface StreamRunInput {
        type: "human";
        content: string;
    }

    /** Request body for starting a normal streaming run. */
    interface StreamRunRequest {
        thread_id?: string | null; // Optional: Only sent for existing threads
        input: StreamRunInput;
        constitutions: SelectedConstitution[]; // Use the new union type including title and adherence_level
        // Removed: adherence_levels_text?: string; // This field is removed as per plan
    }

    /** Defines a set of constitutions for comparison. */
    interface CompareSet {
        id: string; // User-defined ID for the set (e.g., 'strict_vs_default')
        // This might need updating later if compare mode needs adherence levels + titles
        constitutions: Array<{ id: string } | { text: string }>; // Simplified for now, assuming no adherence/title needed for compare yet
        // name?: string; // Optional name, not used by backend currently
    }

    /** Request body for starting a comparison streaming run. */
    interface CompareRunRequest {
        thread_id?: string | null; // Optional: Only sent for existing threads
        input: StreamRunInput;
        constitution_sets: CompareSet[];
    }


    // --- Server-Sent Event (SSE) Data Types ---

    /** Structure for the initial thread creation event */
    interface SSEThreadCreatedData {
        thread_id: string; // The backend's newly created persistent thread ID
    }

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
        thread_id: string; // Backend's definitive thread ID (UUID string)
    }

    /** Overall structure of data received via SSE */
    interface SSEEventData {
        type: "thread_created" | "chunk" | "ai_tool_chunk" | "tool_result" | "error" | "end";
        node?: string | null; // Graph node where event originated
        // Type of data depends on the 'type' field
        data: SSEThreadCreatedData | string | SSEToolCallChunkData | SSEToolResultData | SSEEndData | any; // Allow flexibility for 'chunk' (string) or 'error' (any)
        set_id?: string | null; // Identifier for compare mode sets
    }

    // SSEMessageHandler type removed - will be redefined or inferred in api.ts if needed

    // --- Other API Types ---
    /** Request body for submitting a new constitution */
    interface ConstitutionSubmission {
        text: string;
        is_private: boolean;
    }

    /** Response from submitting a new constitution */
    interface SubmissionResponse {
        status: string;
        message: string;
        email_sent: boolean;
    }

    /** User information obtained from the backend after authentication */
    interface UserInfo {
        email?: string | null; // Optional email
        name?: string | null; // Optional name
        picture?: string | null; // Optional URL to profile picture
    }

    // --- Application State/Mode Types ---
    type AppMode = 'chat' | 'use' | 'compare'; // Still relevant if UI uses modes? Sidebar removed it.

    /** Represents the state of a single conversation in the UI */
    interface ConversationState {
        metadata: ConversationMetadata; // From conversationManager
        messages: MessageType[];
        status: 'idle' | 'loading_history' | 'streaming' | 'error'; // Granular status
        error?: string; // Error specific to this conversation
        abortController?: AbortController; // Controller for ongoing fetch/stream
    }
}

// Ensures this file is treated as a module. Required for declare global.
export { };

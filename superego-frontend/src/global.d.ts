
declare global {
    interface UISessionState {
        sessionId: string;
        name: string;
        createdAt: string;
        lastUpdatedAt: string;
        threadIds: string[];
    }

    interface ConfiguredConstitutionModule {
        id: string;
        title: string;
        adherence_level: number;
        text?: string;
    }

    interface RunConfig {
        configuredModules: ConfiguredConstitutionModule[];
    }

    interface CheckpointConfigurable {
        thread_id: string | null;
        runConfig: RunConfig;
    }

    interface HistoryEntry {
        checkpoint_id: string;
        thread_id: string;
        values: {
            messages: MessageType[];
        };
        runConfig: RunConfig;
    }

    /** Represents a single constitution available for selection. */
    interface ConstitutionItem {
        id: string;
        title: string; // Changed from name to title
        description?: string;
    }

    // ThreadItem removed

    interface BaseApiMessage {
        type: 'human' | 'ai' | 'system' | 'tool';
        content: string | any;
        name?: string;
        tool_call_id?: string;
        additional_kwargs?: Record<string, any>;
    }

    interface HumanApiMessage extends BaseApiMessage {
        type: 'human';
        content: string;
    }

    interface AiApiMessage extends BaseApiMessage {
        type: 'ai';
        content: string | any;
        tool_calls?: Array<{ id: string; name: string; args: Record<string, any>; }>;
        invalid_tool_calls?: any[];
    }

    interface SystemApiMessage extends BaseApiMessage {
        type: 'system';
        content: string;
    }

    interface ToolApiMessage extends BaseApiMessage {
        type: 'tool';
        content: string | any;
        tool_call_id: string;
        name?: string;
        is_error?: boolean;
    }

    /** Represents message types received from the backend API. */
    type MessageType = HumanApiMessage | AiApiMessage | SystemApiMessage | ToolApiMessage;


    // HistoryResponse removed

    /** Represents a constitution stored locally in localStorage */
    interface LocalConstitution {
        id: string; // Unique local ID (e.g., UUID)
        title: string;
        text: string;
        createdAt: string; // ISO timestamp string
        // Add lastUpdatedAt?
    }

    // BackendConstitutionRefById, BackendConstitutionFullText, SelectedConstitution removed

    /** Input structure for starting a run */
    interface StreamRunInput {
        type: "human";
        content: string;
    }

    // StreamRunRequest removed
    // CompareSet removed
    // CompareRunRequest removed


    // --- Server-Sent Event (SSE) Data Types ---

    /** Structure for the event carrying the new thread ID */
    interface SSEThreadInfoData {
        thread_id: string; // The backend's newly created or confirmed persistent thread ID
    }

    // SSEThreadCreatedData removed as SSEThreadInfoData serves the purpose

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
        type: "thread_info" | "chunk" | "ai_tool_chunk" | "tool_result" | "error" | "end"; // Added 'thread_info'
        node?: string | null; // Graph node where event originated
        thread_id?: string | null; // Added top-level thread_id for routing (CRITICAL)
        // Type of data depends on the 'type' field
        data: SSEThreadInfoData | string | SSEToolCallChunkData | SSEToolResultData | SSEEndData | any; // Added SSEThreadInfoData, allow flexibility for 'chunk' (string) or 'error' (any)
        set_id?: string | null; // Identifier for compare mode sets (Future use)
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

    /** Represents the state of a single conversation in the UI */
    interface ConversationState {
        metadata: ConversationMetadata; // From conversationManager
        messages: MessageType[];
        status: 'idle' | 'loading_history' | 'streaming' | 'error'; // Granular status
        error?: string; // Error specific to this conversation
        abortController?: AbortController; // Controller for ongoing fetch/stream
    }
    // ConversationState removed
}

// Ensures this file is treated as a module. Required for declare global.
export { };

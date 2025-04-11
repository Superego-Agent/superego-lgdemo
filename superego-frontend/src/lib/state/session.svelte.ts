import { v4 as uuidv4 } from 'uuid';

// --- Constants for LocalStorage Keys ---
const KNOWN_THREADS_KEY = 'superego_knownThreads';
const UI_SESSIONS_KEY = 'superego_uiSessions';
const ACTIVE_SESSION_ID_KEY = 'superego_activeSessionId';

// --- Helper function to safely get item from localStorage ---
function getLocalStorageItem<T>(key: string, defaultValue: T): T {
    const item = localStorage.getItem(key);
    if (item != null) {
        try {
            return JSON.parse(item) as T;
        } catch (e) {
            console.error(`Error parsing localStorage item "${key}":`, e);
            // Fallback to default value if parsing fails
            return defaultValue;
        }
    }
    return defaultValue;
}

// --- Helper function to safely set item in localStorage ---
function setLocalStorageItem<T>(key: string, value: T): void {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.error(`Error setting localStorage item "${key}":`, e);
    }
}


export class SessionStateStore {
    // --- Core State Properties ---

    /** List of all LangGraph thread IDs known to this client. Acts as an index. */
    knownThreadIds = $state<string[]>(getLocalStorageItem(KNOWN_THREADS_KEY, []));

    /** Holds state for ALL UI sessions/tabs, keyed by sessionId. Maps UI tabs to backend thread IDs. */
    uiSessions = $state<Record<string, UISessionState>>(getLocalStorageItem(UI_SESSIONS_KEY, {}));

    /** Tracks the sessionId of the currently viewed session/tab */
    activeSessionId = $state<string | null>(getLocalStorageItem(ACTIVE_SESSION_ID_KEY, null));

    constructor() {
        // --- Persistence Effects ---
        // Use $effect to automatically save state changes to localStorage

        $effect(() => {
            setLocalStorageItem(KNOWN_THREADS_KEY, this.knownThreadIds);
        });

        $effect(() => {
            setLocalStorageItem(UI_SESSIONS_KEY, this.uiSessions);
        });

        $effect(() => {
            setLocalStorageItem(ACTIVE_SESSION_ID_KEY, this.activeSessionId);
        });
    }

    // --- Methods for State Mutation ---
    /**
     * Creates a new UI session, adds it to the store, and sets it as active.
     * @param name Optional initial name for the session. Defaults to "New Session".
     * @returns The newly created UISessionState object.
     */
    createNewSession(name: string = "New Session"): UISessionState {
        const newSessionId = uuidv4();
        const now = new Date().toISOString();
        // Create default config first
        const defaultThreadId = uuidv4();
        const defaultThreadConfig: ThreadConfigState = {
            name: "Config 1",
            runConfig: { configuredModules: [] },
            isEnabled: true
        };

        const newSession: UISessionState = {
            sessionId: newSessionId,
            name: name,
            createdAt: now,
            lastUpdatedAt: now,
            threads: { [defaultThreadId]: defaultThreadConfig } // Initialize with default
        };

        this.uiSessions[newSessionId] = newSession;
        this.activeSessionId = newSessionId;
        // Assuming uiState is accessible or passed in if needed for activeConfigEditorId
        // uiState.activeConfigEditorId = defaultThreadId; // This needs uiState access
        console.log(`[OK] Created new session: ${newSessionId} (${name})`);
        return newSession;
    }

    /**
     * Renames an existing UI session.
     * @param sessionId The ID of the session to rename.
     * @param newName The new name for the session.
     */
    renameSession(sessionId: string, newName: string): void {
        const sessionToRename = this.uiSessions[sessionId];
        if (sessionToRename) {
            sessionToRename.name = newName;
            sessionToRename.lastUpdatedAt = new Date().toISOString();
            console.log(`[OK] Renamed session ${sessionId} to "${newName}"`);
        } else {
             console.warn(`Attempted rename on non-existent session: ${sessionId}`);
        }
    }

    /**
     * Deletes a UI session. If the deleted session was active, it resets the active session ID.
     * @param sessionId The ID of the session to delete.
     */
    deleteSession(sessionId: string): void {
        if (!this.uiSessions[sessionId]) {
            console.warn(`Attempted to delete non-existent session: ${sessionId}`);
            return;
        }

        delete this.uiSessions[sessionId];
        console.log(`[OK] Deleted session: ${sessionId}`);

        if (this.activeSessionId === sessionId) {
            const remainingIds = Object.keys(this.uiSessions);
            this.activeSessionId = remainingIds.length > 0 ? remainingIds[0] : null;
            console.log(`[OK] Active session was deleted. New active session: ${this.activeSessionId}`);
        }
    }

    /**
     * Adds a backend thread ID to a specific UI session's known threads and updates timestamp.
     * Also ensures the thread ID is added to the global knownThreadIds list.
     * Note: This function assumes the thread *config* itself is added/managed elsewhere.
     * @param sessionId The ID of the UI session.
     * @param threadId The backend thread ID to associate.
     */
    addThreadToSession(sessionId: string, threadId: string): void {
        this.addKnownThreadId(threadId); // Ensure it's known globally

        const sessionToAddThread = this.uiSessions[sessionId];
        if (sessionToAddThread) {
            // Just update timestamp, actual thread config management is separate
            sessionToAddThread.lastUpdatedAt = new Date().toISOString();
            console.log(`[OK] Associated thread ${threadId} with session ${sessionId} (updated timestamp)`);
        } else {
            console.warn(`Attempted addThreadToSession on non-existent session: ${sessionId}`);
        }
    }

    /**
     * Removes a backend thread ID from a specific UI session.
     * Note: This does not remove the thread ID from the global knownThreadIds.
     * @param sessionId The ID of the UI session.
     * @param threadId The backend thread ID to remove.
     */
    removeThreadFromSession(sessionId: string, threadId: string): void {
        const sessionToRemoveFrom = this.uiSessions[sessionId];
        if (sessionToRemoveFrom?.threads?.[threadId]) {
            delete sessionToRemoveFrom.threads[threadId];
            sessionToRemoveFrom.lastUpdatedAt = new Date().toISOString();
            console.log(`[OK] Removed thread ${threadId} from session ${sessionId}`);
            // Also check if the removed thread was the active editor - requires uiState access
            // if (uiState.activeConfigEditorId === threadId) {
            //     const remainingThreadIds = Object.keys(sessionToRemoveFrom.threads);
            //     uiState.activeConfigEditorId = remainingThreadIds.length > 0 ? remainingThreadIds[0] : null;
            //     console.log(`[OK] Active config editor was removed. New active editor: ${uiState.activeConfigEditorId}`);
            // }
        } else {
             console.warn(`Attempted removeThreadFromSession for non-existent session ${sessionId} or thread ${threadId}`);
        }
    }

    /**
     * Adds a thread ID to the global list of known thread IDs if not already present.
     * @param threadId The thread ID to add.
     */
    addKnownThreadId(threadId: string): void {
       if (!this.knownThreadIds.includes(threadId)) {
           this.knownThreadIds.push(threadId);
           console.log(`[OK] Added thread ${threadId} to knownThreadIds`);
       }
    }

    /**
     * Sets the active session ID.
     * @param sessionId The ID of the session to set as active, or null.
     */
    setActiveSessionId(sessionId: string | null): void {
        this.activeSessionId = sessionId;
        console.log(`[OK] Set active session ID to: ${sessionId}`);
    }

    // TODO: Add methods to manage sessions, threads etc.
    // e.g., addKnownThreadId, removeKnownThreadId, updateUiSession, setActiveSessionId

    // --- Derived State (Examples - Add as needed) ---

    get activeUiSession(): UISessionState | undefined {
        return this.activeSessionId ? this.uiSessions[this.activeSessionId] : undefined;
    }

    // Add other derived state or methods as required by the application logic
}

// --- Export Singleton Instance ---
export const sessionState = new SessionStateStore();
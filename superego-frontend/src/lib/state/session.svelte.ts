import { v4 as uuidv4 } from 'uuid';
// Removed nanoid import
import { persistedLocalState } from '$lib/utils/persistedLocalState.svelte';

// --- Constants for LocalStorage Keys ---
const KNOWN_THREADS_KEY = 'superego_knownThreads';
const UI_SESSIONS_KEY = 'superego_uiSessions';
const ACTIVE_SESSION_ID_KEY = 'superego_activeSessionId';
// Removed LOCAL_CONSTITUTIONS_KEY

// Removed manual localStorage helper functions


export class SessionStateStore {
    // --- Core State Properties ---

    /** List of all LangGraph thread IDs known to this client. Acts as an index. Persisted. */
    knownThreadIds = persistedLocalState<string[]>(KNOWN_THREADS_KEY, []);

    /** Holds state for ALL UI sessions/tabs, keyed by sessionId. Maps UI tabs to backend thread IDs. Persisted. */
    uiSessions = persistedLocalState<Record<string, UISessionState>>(UI_SESSIONS_KEY, {});

    /** Tracks the sessionId of the currently viewed session/tab. Persisted. */
    activeSessionId = persistedLocalState<string | null>(ACTIVE_SESSION_ID_KEY, null);

    // Removed localConstitutions property

    // Constructor no longer needs manual persistence effects
    constructor() {}

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

        // Use .state to access/mutate the wrapped state
        this.uiSessions.state = { ...this.uiSessions.state, [newSessionId]: newSession };
        this.activeSessionId.state = newSessionId;
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
        const sessionToRename = this.uiSessions.state[sessionId];
        if (sessionToRename) {
            const updatedSession = { ...sessionToRename, name: newName, lastUpdatedAt: new Date().toISOString() };
            this.uiSessions.state = { ...this.uiSessions.state, [sessionId]: updatedSession };
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
        if (!this.uiSessions.state[sessionId]) {
            console.warn(`Attempted to delete non-existent session: ${sessionId}`);
            return;
        }

        const currentSessions = { ...this.uiSessions.state };
        delete currentSessions[sessionId];
        this.uiSessions.state = currentSessions;
        console.log(`[OK] Deleted session: ${sessionId}`);

        if (this.activeSessionId.state === sessionId) {
            const remainingIds = Object.keys(this.uiSessions.state);
            this.activeSessionId.state = remainingIds.length > 0 ? remainingIds[0] : null;
            console.log(`[OK] Active session was deleted. New active session: ${this.activeSessionId.state}`);
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

        const sessionToAddThread = this.uiSessions.state[sessionId];
        if (sessionToAddThread) {
            // Just update timestamp
            const updatedSession = { ...sessionToAddThread, lastUpdatedAt: new Date().toISOString() };
            this.uiSessions.state = { ...this.uiSessions.state, [sessionId]: updatedSession };
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
        const sessionToRemoveFrom = this.uiSessions.state[sessionId];
        if (sessionToRemoveFrom?.threads?.[threadId]) {
            const updatedThreads = { ...sessionToRemoveFrom.threads };
            delete updatedThreads[threadId];
            const updatedSession = { ...sessionToRemoveFrom, threads: updatedThreads, lastUpdatedAt: new Date().toISOString() };
            this.uiSessions.state = { ...this.uiSessions.state, [sessionId]: updatedSession };
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
       if (!this.knownThreadIds.state.includes(threadId)) {
           this.knownThreadIds.state = [...this.knownThreadIds.state, threadId];
           console.log(`[OK] Added thread ${threadId} to knownThreadIds.state`);
       }
    }

    /**
     * Sets the active session ID.
     * @param sessionId The ID of the session to set as active, or null.
     */
    setActiveSessionId(sessionId: string | null): void {
        this.activeSessionId.state = sessionId;
        console.log(`[OK] Set active session ID to: ${sessionId}`);
    }

    // Removed Local Constitution Methods

    // --- Derived State ---

    get activeUiSession(): UISessionState | undefined {
        // Access persisted state via .state
        return this.activeSessionId.state ? this.uiSessions.state[this.activeSessionId.state] : undefined;
    }

    // Add other derived state or methods as required
}

// --- Export Singleton Instance ---
export const sessionStore = new SessionStateStore();
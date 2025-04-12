import { v4 as uuidv4 } from 'uuid';
import { persistedLocalState, PersistedLocalState } from '$lib/utils/persistedLocalState.svelte'; 
// Removed imports related to the misplaced effect

// --- Constants for LocalStorage Keys ---
const THREAD_IDS_WITH_BACKEND_HISTORY_KEY = 'superego_threadIdsWithBackendHistory'; // Renamed from DISPATCHED_THREADS_KEY
const UI_SESSIONS_KEY = 'superego_uiSessions';
const ACTIVE_SESSION_ID_KEY = 'superego_activeSessionId';

export class SessionStateStore {
    // --- Core State Properties ---

    // --- Helper to define persisted properties ---
    #definePersisted<T>(propName: keyof this, storageKey: string, defaultValue: T): PersistedLocalState<T> {
        const persisted = persistedLocalState<T>(storageKey, defaultValue);
        Object.defineProperty(this, propName, {
            get: () => persisted.state,
            set: (value: T) => { persisted.state = value; },
            enumerable: true,
            configurable: true
        });
        return persisted;
    }

    // --- Public Property Declarations (Initialized in constructor) ---
    threadIdsWithBackendHistory: string[] = []; // Renamed from dispatchedThreadIds
    uiSessions: Record<string, UISessionState> = {};
    activeSessionId: string | null = null;

    constructor() {
        this.#definePersisted('threadIdsWithBackendHistory', THREAD_IDS_WITH_BACKEND_HISTORY_KEY, []);
        this.#definePersisted('uiSessions', UI_SESSIONS_KEY, {});
        this.#definePersisted('activeSessionId', ACTIVE_SESSION_ID_KEY, null);
        // Ensure initial active session is valid if loaded from storage
        if (this.activeSessionId && !this.uiSessions[this.activeSessionId]) {
            console.warn(`[INIT] Stored activeSessionId (${this.activeSessionId}) not found in uiSessions. Resetting.`);
            this.activeSessionId = Object.keys(this.uiSessions)[0] || null;
        }
        console.log('[INIT] SessionStateStore initialized.');
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

        // Use direct property access (triggers setter)
        this.uiSessions = { ...this.uiSessions, [newSessionId]: newSession };
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
        // Use direct property access (triggers getter/setter)
        const sessionToRename = this.uiSessions[sessionId];
        if (sessionToRename) {
            const updatedSession = { ...sessionToRename, name: newName, lastUpdatedAt: new Date().toISOString() };
            this.uiSessions = { ...this.uiSessions, [sessionId]: updatedSession };
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
        if (!this.uiSessions[sessionId]) { // Use direct access
            console.warn(`Attempted to delete non-existent session: ${sessionId}`);
            return;
        }

        // Use direct access and immutable update
        const currentSessions = { ...this.uiSessions };
        delete currentSessions[sessionId];
        this.uiSessions = currentSessions;
        console.log(`[OK] Deleted session: ${sessionId}`);

        // Use direct access
        if (this.activeSessionId === sessionId) {
            const remainingIds = Object.keys(this.uiSessions);
            this.activeSessionId = remainingIds.length > 0 ? remainingIds[0] : null;
            console.log(`[OK] Active session was deleted. New active session: ${this.activeSessionId}`);
        }
    }

    /**
     * Adds a backend thread ID to a specific UI session's known threads and updates timestamp.
     * Also ensures the thread ID is added to the global threadIdsWithBackendHistory list.
     * Note: This function assumes the thread *config* itself is added/managed elsewhere.
     * @param sessionId The ID of the UI session.
     * @param threadId The backend thread ID to associate.
     */
    addThreadToSession(sessionId: string, threadId: string): void {
        this.addThreadIdWithBackendHistory(threadId); // Ensure it's known globally

        // Use direct access and immutable update
        const sessionToAddThread = this.uiSessions[sessionId];
        if (sessionToAddThread) {
            const updatedSession = { ...sessionToAddThread, lastUpdatedAt: new Date().toISOString() };
            this.uiSessions = { ...this.uiSessions, [sessionId]: updatedSession };
            console.log(`[OK] Associated thread ${threadId} with session ${sessionId} (updated timestamp)`);
        } else {
            console.warn(`Attempted addThreadToSession on non-existent session: ${sessionId}`);
        }
    }

    /**
     * Removes a backend thread ID from a specific UI session.
     * Note: This does not remove the thread ID from the global threadIdsWithBackendHistory.
     * @param sessionId The ID of the UI session.
     * @param threadId The backend thread ID to remove.
     */
    removeThreadFromSession(sessionId: string, threadId: string): void {
        // Use direct access and immutable update
        const sessionToRemoveFrom = this.uiSessions[sessionId];
        if (sessionToRemoveFrom?.threads?.[threadId]) {
            const updatedThreads = { ...sessionToRemoveFrom.threads };
            delete updatedThreads[threadId];
            const updatedSession = { ...sessionToRemoveFrom, threads: updatedThreads, lastUpdatedAt: new Date().toISOString() };
            this.uiSessions = { ...this.uiSessions, [sessionId]: updatedSession };
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
     * Adds a thread ID to the global list of thread IDs known to have backend history if not already present.
     * @param threadId The thread ID to add.
     */
    addThreadIdWithBackendHistory(threadId: string): void { // Renamed from addDispatchedThreadId
       // Use direct access (getter/setter)
       if (!this.threadIdsWithBackendHistory.includes(threadId)) {
           this.threadIdsWithBackendHistory = [...this.threadIdsWithBackendHistory, threadId]; // Setter handles persistence
       }
    }

    /**
     * Sets the active session ID.
     * @param sessionId The ID of the session to set as active, or null.
     */
    setActiveSessionId(sessionId: string | null): void {
        // Use direct access (setter)
        this.activeSessionId = sessionId;
        // console.log(`[OK] Set active session ID to: ${sessionId}`); // Original log replaced by the one below
        const sessionData = sessionId ? this.uiSessions[sessionId] : null;
        // Restore original log structure for now
        console.log(`[OK] Set active session ID to: ${sessionId}. Associated threads:`, sessionData?.threads ? Object.keys(sessionData.threads) : 'None');
    }

    // Removed Local Constitution Methods

    // --- Derived State ---

    get activeUiSession(): UISessionState | undefined {
        // Use direct property access (triggers getters)
        return this.activeSessionId ? this.uiSessions[this.activeSessionId] : undefined;
    }

    // Removed duplicate constructor and misplaced $effect logic (placeholder)
}

// --- Export Singleton Instance ---
export const sessionStore = new SessionStateStore();
import { v4 as uuidv4 } from 'uuid';
import { persistedLocalState, PersistedLocalState } from '$lib/utils/persistedLocalState.svelte'; 

// --- Constants for LocalStorage Keys ---
const KNOWN_THREADS_KEY = 'superego_knownThreads';
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

    // --- Public Property Declarations (Types) ---
    // Definite assignment assertion '!' used as they are initialized in constructor via helper
    knownThreadIds!: string[];
    uiSessions!: Record<string, UISessionState>;
    activeSessionId!: string | null;

    // Constructor no longer needs manual persistence effects
    constructor() {
        // Initialize persisted properties using the helper
        this.#definePersisted('knownThreadIds', KNOWN_THREADS_KEY, []);
        this.#definePersisted('uiSessions', UI_SESSIONS_KEY, {});
        this.#definePersisted('activeSessionId', ACTIVE_SESSION_ID_KEY, null);
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
     * Also ensures the thread ID is added to the global knownThreadIds list.
     * Note: This function assumes the thread *config* itself is added/managed elsewhere.
     * @param sessionId The ID of the UI session.
     * @param threadId The backend thread ID to associate.
     */
    addThreadToSession(sessionId: string, threadId: string): void {
        this.addKnownThreadId(threadId); // Ensure it's known globally

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
     * Note: This does not remove the thread ID from the global knownThreadIds.
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
     * Adds a thread ID to the global list of known thread IDs if not already present.
     * @param threadId The thread ID to add.
     */
    addKnownThreadId(threadId: string): void {
       // Use direct access (getter/setter)
       if (!this.knownThreadIds.includes(threadId)) {
           this.knownThreadIds = [...this.knownThreadIds, threadId]; // Setter handles persistence
           console.log(`[OK] Added thread ${threadId} to knownThreadIds`);
       }
    }

    /**
     * Sets the active session ID.
     * @param sessionId The ID of the session to set as active, or null.
     */
    setActiveSessionId(sessionId: string | null): void {
        // Use direct access (setter)
        this.activeSessionId = sessionId;
        console.log(`[OK] Set active session ID to: ${sessionId}`);
    }

    // Removed Local Constitution Methods

    // --- Derived State ---

    get activeUiSession(): UISessionState | undefined {
        // Use direct property access (triggers getters)
        return this.activeSessionId ? this.uiSessions[this.activeSessionId] : undefined;
    }

    // Add other derived state or methods as required
}

// --- Export Singleton Instance ---
export const sessionStore = new SessionStateStore();
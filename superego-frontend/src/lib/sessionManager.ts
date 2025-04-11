// import { get } from 'svelte/store'; // Removed
import { v4 as uuidv4 } from 'uuid';
import { persistedUiSessions, persistedActiveSessionId, persistedKnownThreadIds } from './stores.svelte'; // Import renamed state instances
import { uiState } from './stores/uiState.svelte';
import { logOperationStatus } from './utils'; // Keep for now

/**
 * Creates a new UI session, adds it to the store, and sets it as active.
 * @param name Optional initial name for the session. Defaults to "New Session".
 * @returns The newly created UISessionState object.
 */
export function createNewSession(name: string = "New Session"): UISessionState {
    // This operation always succeeds if it runs, keep specific log
    const newSessionId = uuidv4();
    const now = new Date().toISOString();
    // Create default config first
    const defaultThreadId = uuidv4();
    const defaultThreadConfig: ThreadConfigState = {
        name: "Default Config",
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

    persistedUiSessions.state[newSessionId] = newSession;
    persistedActiveSessionId.state = newSessionId;
    uiState.activeConfigEditorId = defaultThreadId;
    console.log(`[OK] Created new session: ${newSessionId} (${name})`);
    return newSession;
}

/**
 * Renames an existing UI session.
 * @param sessionId The ID of the session to rename.
 * @param newName The new name for the session.
 */
export function renameSession(sessionId: string, newName: string): void {
    // Direct mutation
    const sessionToRename = persistedUiSessions.state[sessionId];
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
export function deleteSession(sessionId: string): void {
    // Deletion is specific, keep direct logging
    // Direct check and mutation/assignment
    if (!persistedUiSessions.state[sessionId]) {
        console.warn(`Attempted to delete non-existent session: ${sessionId}`);
        return;
    }

    delete persistedUiSessions.state[sessionId];
    console.log(`[OK] Deleted session: ${sessionId}`);

    if (persistedActiveSessionId.state === sessionId) {
        const remainingIds = Object.keys(persistedUiSessions.state);
        persistedActiveSessionId.state = remainingIds.length > 0 ? remainingIds[0] : null;
        console.log(`[OK] Active session was deleted. New active session: ${persistedActiveSessionId.state}`);
    }
}

/**
 * Adds a backend thread ID to a specific UI session.
 * Also ensures the thread ID is added to the knownThreadIds list.
 * @param sessionId The ID of the UI session.
 * @param threadId The backend thread ID to add.
 */
export function addThreadToSession(sessionId: string, threadId: string): void {
    // Direct mutation for knownThreadIds
    if (!persistedKnownThreadIds.state.includes(threadId)) {
        persistedKnownThreadIds.state.push(threadId);
         console.log(`[OK] Added thread ${threadId} to knownThreadIds`);
    }

    // Direct mutation for session timestamp
    const sessionToAddThread = persistedUiSessions.state[sessionId];
    if (sessionToAddThread) {
        // If thread doesn't exist yet in this session, add it (Phase 2 will refine this)
        if (!sessionToAddThread.threads[threadId]) {
             console.warn(`Thread ${threadId} not found in session ${sessionId} during addThreadToSession, only updating timestamp.`);
        }
        sessionToAddThread.lastUpdatedAt = new Date().toISOString();
        console.log(`[OK] Associated thread ${threadId} with session ${sessionId} (updated timestamp)`);
    } else {
        console.warn(`Attempted addThreadToSession on non-existent session: ${sessionId}`);
    }
}

/**
 * Removes a backend thread ID from a specific UI session.
 * Note: This does not remove the thread ID from knownThreadIds.
 * @param sessionId The ID of the UI session.
 * @param threadId The backend thread ID to remove.
 */
export function removeThreadFromSession(sessionId: string, threadId: string): void {
    const sessionToRemoveFrom = persistedUiSessions.state[sessionId];
    if (sessionToRemoveFrom?.threads?.[threadId]) {
        delete sessionToRemoveFrom.threads[threadId];
        sessionToRemoveFrom.lastUpdatedAt = new Date().toISOString();
        console.log(`[OK] Removed thread ${threadId} from session ${sessionId}`);
        // Also check if the removed thread was the active editor
        if (uiState.activeConfigEditorId === threadId) {
            const remainingThreadIds = Object.keys(sessionToRemoveFrom.threads);
            uiState.activeConfigEditorId = remainingThreadIds.length > 0 ? remainingThreadIds[0] : null;
            console.log(`[OK] Active config editor was removed. New active editor: ${uiState.activeConfigEditorId}`);
        }
    } else {
         console.warn(`Attempted removeThreadFromSession for non-existent session ${sessionId} or thread ${threadId}`);
    }
}

/**
 * Adds a thread ID to the global list of known thread IDs if not already present.
 * @param threadId The thread ID to add.
 */
export function addKnownThreadId(threadId: string): void {
   // Direct mutation
   if (!persistedKnownThreadIds.state.includes(threadId)) {
       persistedKnownThreadIds.state.push(threadId);
       console.log(`[OK] Added thread ${threadId} to knownThreadIds`);
   }
}


// src/lib/sessionManager.ts
import { get } from 'svelte/store';
import { v4 as uuidv4 } from 'uuid';
import { uiSessions, activeSessionId, knownThreadIds } from './stores';
import { logOperationStatus } from './utils'; // Import the helper

/** Helper to safely update a session if it exists - returns boolean for logging */
function _updateSessionIfExists(
    sessionId: string,
    updateFn: (session: UISessionState) => UISessionState | void
): boolean {
    let updated = false;
    uiSessions.update(sessions => {
        const session = sessions[sessionId];
        if (session) {
            const result = updateFn(session);
            sessions[sessionId] = result === undefined ? session : result;
            updated = true; // Mark as updated if session was found and callback executed
        } else {
            console.warn(`Attempted operation on non-existent session: ${sessionId}`);
            // updated remains false
        }
        return sessions;
    });
    return updated; // Return true if the session existed and was processed
}

/** Helper to update known threads - returns boolean for logging */
function _addKnownThreadIdInternal(threadId: string): boolean {
    let added = false;
    knownThreadIds.update(ids => {
        if (!ids.includes(threadId)) {
            ids.push(threadId);
            added = true;
        }
        return ids;
    });
    return added;
}


/**
 * Creates a new UI session, adds it to the store, and sets it as active.
 * @param name Optional initial name for the session. Defaults to "New Session".
 * @returns The newly created UISessionState object.
 */
export function createNewSession(name: string = "New Session"): UISessionState {
    // This operation always succeeds if it runs, keep specific log
    const newSessionId = uuidv4();
    const now = new Date().toISOString();
    const newSession: UISessionState = {
        sessionId: newSessionId,
        name: name,
        createdAt: now,
        lastUpdatedAt: now,
        threadIds: []
    };

    uiSessions.update(sessions => {
        sessions[newSessionId] = newSession;
        return sessions;
    });
    activeSessionId.set(newSessionId); // Automatically activate
    console.log(`[OK] Created new session: ${newSessionId} (${name})`);
    return newSession;
}

/**
 * Renames an existing UI session.
 * @param sessionId The ID of the session to rename.
 * @param newName The new name for the session.
 */
export function renameSession(sessionId: string, newName: string): void {
    logOperationStatus(`Rename session ${sessionId} to "${newName}"`, () =>
        _updateSessionIfExists(sessionId, (session) => {
            session.name = newName;
            session.lastUpdatedAt = new Date().toISOString();
        })
    );
}

/**
 * Deletes a UI session. If the deleted session was active, it resets the active session ID.
 * @param sessionId The ID of the session to delete.
 */
export function deleteSession(sessionId: string): void {
    // Deletion is specific, keep direct logging
    const sessions = get(uiSessions);
    if (!sessions[sessionId]) {
        console.warn(`Attempted to delete non-existent session: ${sessionId}`);
        return;
    }
    uiSessions.update(s => {
        delete s[sessionId];
        console.log(`[OK] Deleted session: ${sessionId}`);
        if (get(activeSessionId) === sessionId) {
            activeSessionId.set(null);
            console.log(`[OK] Cleared active session ID as it was deleted.`);
        }
        return s;
    });
}

/**
 * Adds a backend thread ID to a specific UI session.
 * Also ensures the thread ID is added to the knownThreadIds list.
 * @param sessionId The ID of the UI session.
 * @param threadId The backend thread ID to add.
 */
export function addThreadToSession(sessionId: string, threadId: string): void {
    logOperationStatus(`Add thread ${threadId} to session ${sessionId}`, () =>
        _updateSessionIfExists(sessionId, (session) => {
            if (!session.threadIds.includes(threadId)) {
                session.threadIds.push(threadId);
                session.lastUpdatedAt = new Date().toISOString();
                // Log adding to known threads separately
                logOperationStatus(`Add thread ${threadId} to knownThreadIds`, () =>
                    _addKnownThreadIdInternal(threadId)
                );
            }
        })
    );
}

/**
 * Removes a backend thread ID from a specific UI session.
 * Note: This does not remove the thread ID from knownThreadIds.
 * @param sessionId The ID of the UI session.
 * @param threadId The backend thread ID to remove.
 */
export function removeThreadFromSession(sessionId: string, threadId: string): void {
    logOperationStatus(`Remove thread ${threadId} from session ${sessionId}`, () =>
        _updateSessionIfExists(sessionId, (session) => {
            const index = session.threadIds.indexOf(threadId);
            if (index > -1) {
                session.threadIds.splice(index, 1);
                session.lastUpdatedAt = new Date().toISOString();
            }
        })
    );
}

/**
 * Adds a thread ID to the global list of known thread IDs if not already present.
 * @param threadId The thread ID to add.
 */
export function addKnownThreadId(threadId: string): void {
     logOperationStatus(`Add thread ${threadId} to knownThreadIds`, () =>
         _addKnownThreadIdInternal(threadId)
     );
}

// Optional: Function to remove a thread ID from knownThreadIds if needed later
// export function removeKnownThreadId(threadId: string): void {
//     logOperationStatus(`Remove thread ${threadId} from knownThreadIds`, () => {
//         let removed = false;
//         knownThreadIds.update(ids => {
//             const index = ids.indexOf(threadId);
//             if (index > -1) {
//                 ids.splice(index, 1);
//                 removed = true;
//             }
//             return ids;
//         });
//         return removed;
//     });
// }

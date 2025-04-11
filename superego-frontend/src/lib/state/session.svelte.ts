import { v4 as uuidv4 } from 'uuid';
import { localStore } from '../utils/localStore.svelte';

// --- Constants ---
const SESSIONS_STORAGE_KEY = 'superego_sessions';
const ACTIVE_SESSION_ID_STORAGE_KEY = 'superego_activeSessionId';
const KNOWN_THREAD_IDS_STORAGE_KEY = 'superego_knownThreadIds';

// --- Default State Creators ---

function createDefaultThreadConfig(name: string = "Default Config"): ThreadConfigState {
    return { name: name, runConfig: { configuredModules: [] }, isEnabled: true };
}

function createDefaultSession(sessionId: string, name: string): UISessionState {
     const now = new Date().toISOString();
     return { sessionId: sessionId, name: name, createdAt: now, lastUpdatedAt: now, threads: {} };
}

// --- Core Reactive State (Persisted via LocalStore) ---

let storedSessions = localStore<Record<string, UISessionState>>(SESSIONS_STORAGE_KEY, {});
let storedActiveSessionId = localStore<string | null>(ACTIVE_SESSION_ID_STORAGE_KEY, null);
let storedKnownThreadIds = localStore<string[]>(KNOWN_THREAD_IDS_STORAGE_KEY, []);


// --- Internal Session Modification Helper ---

/** Gets a session, calls the modifier function, and updates timestamp. */
function _modifySession(sessionId: string, modifier: (session: UISessionState) => void): void {
    const session = storedSessions.value[sessionId];
    if (session) {
        modifier(session);
        session.lastUpdatedAt = new Date().toISOString();
    }
}


// --- Exported Mutation Functions ---

export function createNewSession(name: string = "New Session"): string {
    const newSessionId = uuidv4();
    storedSessions.value[newSessionId] = createDefaultSession(newSessionId, name);
    storedActiveSessionId.value = newSessionId;
    return newSessionId;
}

export function renameSession(sessionId: string, newName: string): void {
    _modifySession(sessionId, (session) => {
        session.name = newName;
    });
}

export function deleteSession(sessionId: string): void {
    if (storedSessions.value[sessionId]) {
        delete storedSessions.value[sessionId];
        if (storedActiveSessionId.value === sessionId) {
            const remainingIds = Object.keys(storedSessions.value);
            storedActiveSessionId.value = remainingIds.length > 0 ? remainingIds[0] : null;
        }
    }
}

export function setActiveSessionId(sessionId: string | null): void {
    if (sessionId === null || storedSessions.value[sessionId]) {
        storedActiveSessionId.value = sessionId;
    }
}

export function addKnownThreadId(threadId: string): void {
    if (!storedKnownThreadIds.value.includes(threadId)) {
        storedKnownThreadIds.value.push(threadId);
    }
}

export function addThreadToSession(sessionId: string, threadId: string): void {
    addKnownThreadId(threadId);
    _modifySession(sessionId, (session) => {
        if (!session.threads[threadId]) {
            session.threads[threadId] = createDefaultThreadConfig(`Config for ${threadId.substring(0, 6)}...`);
        }
        // Helper updates timestamp if session exists
    });
}

export function removeThreadFromSession(sessionId: string, threadId: string): void {
    _modifySession(sessionId, (session) => {
        if (session.threads?.[threadId]) {
            delete session.threads[threadId];
        }
    });
}

export function toggleModule(sessionId: string, threadId: string, moduleId: string, moduleTitle: string, isChecked: boolean): void {
    _modifySession(sessionId, (session) => {
        const thread = session.threads?.[threadId];
        if (!thread) return;

        if (!thread.runConfig) thread.runConfig = { configuredModules: [] };
        const modules = thread.runConfig.configuredModules;
        const existingIndex = modules.findIndex((m: ConfiguredConstitutionModule) => m.id === moduleId);

        if (isChecked && existingIndex === -1) {
            modules.push({ id: moduleId, title: moduleTitle, adherence_level: 3 });
        } else if (!isChecked && existingIndex !== -1) {
            modules.splice(existingIndex, 1);
        }
    });
}

export function setAdherenceLevel(sessionId: string, threadId: string, moduleId: string, level: number): void {
    _modifySession(sessionId, (session) => {
        const module = session.threads?.[threadId]?.runConfig?.configuredModules?.find((m: ConfiguredConstitutionModule) => m.id === moduleId);
        if (module) {
            module.adherence_level = level;
        }
    });
}

// --- Derived State (Read-Only Exports) ---

export const sessions = $derived(storedSessions.value);
export const activeSessionId = $derived(storedActiveSessionId.value);
export const knownThreadIds = $derived(storedKnownThreadIds.value);
export const activeSession = $derived(activeSessionId ? sessions[activeSessionId] : null);
export const activeSessionThreadConfigs = $derived(() => {
    const currentSession = activeSession;
    if (!currentSession) return [];
    return Object.entries(currentSession.threads).map(([id, config]: [string, ThreadConfigState]) => ({ threadId: id, ...config }));
});
// Non-persisted application state grouped together
class AppStateStore {
	/**
	 * Central cache holding the latest known state and status for each thread.
	 * Keyed by threadId. NOT persisted.
	 */
	threadCacheStore = $state<Record<string, ThreadCacheData>>({});

	/** Store for displaying global errors */
	globalError = $state<string | null>(null);

	updateThreadCache(updater: (currentCache: Record<string, ThreadCacheData>) => Record<string, ThreadCacheData>) {
		this.threadCacheStore = updater(this.threadCacheStore);
	}

	setThreadCacheEntry(threadId: string, entryData: ThreadCacheData) {
		this.threadCacheStore = { ...this.threadCacheStore, [threadId]: entryData };
	}

	updateThreadCacheEntry(threadId: string, updates: Partial<ThreadCacheData>) {
		if (this.threadCacheStore[threadId]) {
			this.threadCacheStore[threadId] = { ...this.threadCacheStore[threadId], ...updates };
		} else {
			console.warn(`[AppStateStore] Attempted to update non-existent thread cache entry: ${threadId}`);
		}
	}
}
export const appState = new AppStateStore();
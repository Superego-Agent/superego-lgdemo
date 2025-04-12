// State specifically related to managing thread data and cache
class ThreadStateStore {
	/**
	 * Central cache holding the latest known state and status for each thread.
	 * Keyed by threadId. NOT persisted.
	 */
	threadCacheStore = $state<Record<string, ThreadCacheData>>({});

	/**
	 * Replaces the entire thread cache with the result of the updater function.
	 * Use with caution, prefer updateEntry for targeted changes.
	 */
	update(updater: (currentCache: Record<string, ThreadCacheData>) => Record<string, ThreadCacheData>) {
		this.threadCacheStore = updater(this.threadCacheStore);
	}

	/**
	 * Sets or replaces a specific entry in the thread cache.
	 */
	setEntry(threadId: string, entryData: ThreadCacheData) {
		this.threadCacheStore = { ...this.threadCacheStore, [threadId]: entryData };
	}

	/**
	 * Merges partial updates into an existing thread cache entry.
	 * If the entry doesn't exist, it logs a warning and initializes it.
	 */
	updateEntry(threadId: string, updates: Partial<ThreadCacheData>) {
		if (this.threadCacheStore[threadId]) {
			this.threadCacheStore[threadId] = { ...this.threadCacheStore[threadId], ...updates };
		} else {
			// It's possible to receive updates for threads not yet fully loaded (e.g., from history)
			// Initialize if missing, but log a warning as it might indicate an unexpected sequence.
			console.warn(`[ThreadStateStore] Initializing non-existent thread cache entry during update: ${threadId}`);
			// Assuming a minimal structure is needed; adjust if a default factory is more appropriate
			this.threadCacheStore[threadId] = { messages: [], isStreaming: false, isLoading: false, error: null, ...updates } as ThreadCacheData; // Initialize isLoading
		}
	}
}

export const threadStore = new ThreadStateStore();
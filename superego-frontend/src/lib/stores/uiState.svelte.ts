class UIStateStore {
	/**
	 * Tracks the threadId of the configuration card currently being edited
	 */
	activeConfigEditorId = $state<string | null>(null);
}

export const uiState = new UIStateStore();

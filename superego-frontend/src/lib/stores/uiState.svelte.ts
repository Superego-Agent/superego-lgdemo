// UI-specific, non-persisted state
class UIStateStore {
	activeConfigEditorId = $state<string | null>(null);
}

export const uiState = new UIStateStore();

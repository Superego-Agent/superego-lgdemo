// UI-specific, non-persisted state
class UIStateStore {
	activeConfigEditorId = $state<string | null>(null);
}

export const UiStore = new UIStateStore();
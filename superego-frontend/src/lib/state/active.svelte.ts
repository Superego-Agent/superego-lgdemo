import { sessionStore } from '$lib/state/session.svelte'; // Keep import for potential future use if needed elsewhere

// State related to the currently active elements, global status, and UI settings like theme
type Theme = 'light' | 'dark';

class ActiveStateStore {
	/** Store for displaying global errors */
	globalError = $state<string | null>(null);

	/** ID of the configuration currently being edited, or null */
	activeConfigEditorId = $state<string | null>(null); // Default to null

	/** Current theme ('light' or 'dark') */
	theme = $state<Theme>(this.initializeTheme()); // Initialize calls applyTheme

	// Constructor is now empty
	constructor() {}

	/** Applies theme to localStorage and document */
	#applyTheme(themeValue: Theme) {
		if (typeof window !== 'undefined') {
			localStorage.setItem('theme', themeValue);
			document.documentElement.setAttribute('data-theme', themeValue);
			// console.log(`[ActiveStateStore] Theme applied: ${themeValue}`); // Optional: Log for debugging
		}
	}

	/** Initializes theme from localStorage or defaults, applying it immediately */
	private initializeTheme(): Theme {
		let initialThemeValue: Theme = 'light'; // Default
		if (typeof window !== 'undefined') {
			const storedTheme = localStorage.getItem('theme');
			if (storedTheme === 'light' || storedTheme === 'dark') {
				initialThemeValue = storedTheme;
			}
			// Apply the determined theme immediately during initialization
			this.#applyTheme(initialThemeValue);
		}
		return initialThemeValue;
	}

	/** Toggles the theme between 'light' and 'dark' and applies the change */
	toggleTheme(): void {
		const newTheme = this.theme === 'light' ? 'dark' : 'light';
		this.theme = newTheme;
		this.#applyTheme(newTheme); // Apply side effect directly
	}

    /** Clears the global error message */
    clearGlobalError(): void {
        this.globalError = null;
    }

    /** Sets the global error message */
    setGlobalError(message: string): void {
        this.globalError = message;
    }

    /** Sets the active configuration editor ID */
    setActiveConfigEditor(id: string | null): void {
        // This method simply sets the ID. The logic to ensure a default
        // will be handled elsewhere, likely reacting to session changes.
        this.activeConfigEditorId = id;
    }
}

export const activeStore = new ActiveStateStore();
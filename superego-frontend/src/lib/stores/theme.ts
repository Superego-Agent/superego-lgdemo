import { writable } from 'svelte/store';

// Define theme types
export type Theme = 'light' | 'dark';

// Helper function to apply the theme to the document element
function applyThemeToDocument(themeValue: Theme) {
  if (typeof document !== 'undefined') { // Ensure document exists (client-side)
    document.documentElement.setAttribute('data-theme', themeValue);
    // console.log(`Applied theme to document: ${themeValue}`); // Optional debug log
  }
}

// Initialize theme from localStorage if available, otherwise default to 'light'
const initialTheme = (): Theme => {
  if (typeof window !== 'undefined') {
    const storedTheme = localStorage.getItem('theme');
    if (storedTheme === 'light' || storedTheme === 'dark') {
      return storedTheme;
    }
  }
  return 'light';
};

// Create theme store
const initialThemeValue = initialTheme();
export const theme = writable<Theme>(initialThemeValue);

// Apply the initial theme to the document when the module loads
// This ensures the theme is set even before App.svelte mounts
applyThemeToDocument(initialThemeValue);

// Theme toggle function
export function toggleTheme(): void {
  theme.update(currentTheme => {
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    if (typeof window !== 'undefined') {
      localStorage.setItem('theme', newTheme);
    }
    // Apply the new theme to the document immediately after updating the store
    applyThemeToDocument(newTheme);
    return newTheme;
  });
}

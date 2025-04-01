import { writable } from 'svelte/store';

// Define theme types
export type Theme = 'light' | 'dark';

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
export const theme = writable<Theme>(initialTheme());

// Theme toggle function
export function toggleTheme(): void {
  theme.update(currentTheme => {
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    if (typeof window !== 'undefined') {
      localStorage.setItem('theme', newTheme);
    }
    return newTheme;
  });
}

import { writable } from 'svelte/store';
import type { UserInfo } from '../../global.d'; // Corrected path

interface AuthState {
    isAuthenticated: boolean;
    user: UserInfo | null;
    isLoading: boolean;
    error: string | null;
}

const initialState: AuthState = {
    isAuthenticated: false,
    user: null,
    isLoading: true, // Start in loading state until we check
    error: null,
};

const authStore = writable<AuthState>(initialState);

export default {
    subscribe: authStore.subscribe,
    setLoading: (loading: boolean) => {
        authStore.update(state => ({ ...state, isLoading: loading, error: null }));
    },
    setUser: (user: UserInfo) => {
        authStore.update(state => ({
            ...state,
            isAuthenticated: true,
            user: user,
            isLoading: false,
            error: null,
        }));
    },
    setError: (error: string) => {
         authStore.update(state => ({
            ...state,
            isAuthenticated: false,
            user: null,
            isLoading: false,
            error: error,
        }));
    },
    clearUser: () => {
        authStore.update(state => ({
            ...initialState,
            isLoading: false, // No longer loading after logout/clear
        }));
    },
    // Helper to get backend URL (adjust if needed)
    getBackendUrl: () => {
        // In development, Vite proxy handles this, but direct URL needed for login redirect
        // In production, this might be different. Consider using environment variables.
        return import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
    }
};

// Optional: Export the type for convenience elsewhere
export type { AuthState };

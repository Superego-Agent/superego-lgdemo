import { writable } from 'svelte/store';
import type { Writable } from 'svelte/store';

/**
 * Tracks the threadId of the configuration card currently being edited
 */
export const activeConfigEditorId: Writable<string | null> = writable(null);

/** Store for displaying global errors */
export const globalError: Writable<string | null> = writable(null);
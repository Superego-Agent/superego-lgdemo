// src/lib/stores/events.ts
import { writable } from 'svelte/store';

// Event to trigger showing the thread configuration modal
export const showThreadConfigTrigger = writable<boolean>(false);

// Helper to reset the trigger after it's been handled
export function resetThreadConfigTrigger() {
  showThreadConfigTrigger.set(false);
}

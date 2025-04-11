export class PersistedLocalState<T> { 
  _state = $state<T>() as T; // Internal state variable
  key = '';

  constructor(key: string, value: T) {
    this.key = key;
    this._state = value; // Initialize internal state

    // Only access localStorage if in a browser environment
    if (typeof window !== 'undefined') {
        const item = localStorage.getItem(key);
    // Only parse if item exists and is not null/undefined
    if (item != null) { 
    try {
        this._state = this.deserialize(item); // Update internal state
    } catch (e) {
        console.error(`Error deserializing localStorage item "${key}":`, e);
        // Optionally reset to default if deserialization fails
        // localStorage.setItem(this.key, this.serialize(value)); 
        }
    }
} // End browser check for getItem

  }

  get state(): T {
    return this._state; // Return internal state
  }

  set state(newValue: T) {
    this._state = newValue; // Update internal state
    // Only access localStorage if in a browser environment
    if (typeof window !== 'undefined') {
        localStorage.setItem(this.key, this.serialize(newValue)); // Save on set
    }
  }

  // Default serialization/deserialization
  serialize(value: T): string {
    return JSON.stringify(value);
  }

  deserialize(item: string): T {
    return JSON.parse(item);
  }
}

export function persistedLocalState<T>(key: string, value: T) { 
  // Return the class instance directly. Access state via .state
  return new PersistedLocalState(key, value); 
}
export class LocalStore<T> {
  value = $state<T>() as T;
  key = '';

  constructor(key: string, value: T) {
    this.key = key;
    this.value = value;

    const item = localStorage.getItem(key);
    // Only parse if item exists and is not null/undefined
    if (item != null) { 
    try {
        this.value = this.deserialize(item);
    } catch (e) {
        console.error(`Error deserializing localStorage item "${key}":`, e);
        // Optionally reset to default if deserialization fails
        // localStorage.setItem(this.key, this.serialize(value)); 
        }
    }

    $effect(() => {
        localStorage.setItem(this.key, this.serialize(this.value));
    });
  }

  // Default serialization/deserialization
  serialize(value: T): string {
    return JSON.stringify(value);
  }

  deserialize(item: string): T {
    return JSON.parse(item);
  }
}

export function localStore<T>(key: string, value: T) {
  return new LocalStore(key, value);
}
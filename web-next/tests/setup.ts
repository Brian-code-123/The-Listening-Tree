import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Node 25 ships an experimental global `localStorage` with no methods unless a
// storage file is configured, and it shadows jsdom's. Install a plain in-memory
// Storage so the tests behave the same on Node 20 (CI) and newer.
const data = new Map<string, string>();
const memoryStorage: Storage = {
  get length() {
    return data.size;
  },
  clear: () => data.clear(),
  getItem: (key) => data.get(key) ?? null,
  key: (index) => [...data.keys()][index] ?? null,
  removeItem: (key) => void data.delete(key),
  setItem: (key, value) => void data.set(key, String(value)),
};
for (const target of [globalThis, window]) {
  Object.defineProperty(target, 'localStorage', { value: memoryStorage, configurable: true, writable: true });
}

afterEach(() => {
  cleanup();
  localStorage.clear();
});

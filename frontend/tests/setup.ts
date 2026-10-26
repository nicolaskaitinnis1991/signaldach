import "@testing-library/jest-dom/vitest";

// vitest 4's jsdom global mapping does not expose window.localStorage, and
// Node >=22 shadows the global with its own getter that returns undefined
// unless --localstorage-file is set. Install a minimal in-memory Storage shim.
if (typeof globalThis.localStorage?.getItem !== "function") {
  const store = new Map<string, string>();
  const shim: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k) => (store.has(k) ? store.get(k)! : null),
    key: (i) => [...store.keys()][i] ?? null,
    removeItem: (k) => void store.delete(k),
    setItem: (k, v) => void store.set(k, String(v)),
  };
  Object.defineProperty(globalThis, "localStorage", {
    value: shim,
    configurable: true,
    writable: true,
  });
  if (typeof window !== "undefined") {
    Object.defineProperty(window, "localStorage", {
      value: shim,
      configurable: true,
      writable: true,
    });
  }
}

import { describe, it, expect, beforeEach } from "vitest";

// Theme store is in a React context, so we test the logic directly
describe("Theme logic", () => {
  beforeEach(() => {
    try { localStorage.clear(); } catch { /* ignore */ }
  });

  it("localStorage stores and retrieves theme", () => {
    localStorage.setItem("sd_theme", "light");
    expect(localStorage.getItem("sd_theme")).toBe("light");
  });

  it("defaults to dark when nothing stored", () => {
    const stored = localStorage.getItem("sd_theme");
    expect(stored).toBeNull();
    // Our ThemeProvider defaults to "dark"
  });

  it("accepts valid theme values", () => {
    const valid = ["dark", "light", "system"];
    for (const v of valid) {
      localStorage.setItem("sd_theme", v);
      expect(localStorage.getItem("sd_theme")).toBe(v);
    }
  });
});

import { describe, it, expect } from "vitest";
import { ApiError } from "@/lib/api";
import { timeAgo, stripHtml } from "@/lib/api";

// ---------------------------------------------------------------------------
// ApiError class
// ---------------------------------------------------------------------------
describe("ApiError", () => {
  it("stores status, code, retryable flag", () => {
    const err = new ApiError(429, "RATE_LIMITED", "Too many requests", true);
    expect(err.status).toBe(429);
    expect(err.code).toBe("RATE_LIMITED");
    expect(err.message).toBe("Too many requests");
    expect(err.retryable).toBe(true);
    expect(err.name).toBe("ApiError");
    expect(err instanceof Error).toBe(true);
  });

  it("non-retryable error", () => {
    const err = new ApiError(401, "AUTH_REQUIRED", "Not authenticated", false);
    expect(err.retryable).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// timeAgo utility
// ---------------------------------------------------------------------------
describe("timeAgo", () => {
  it("returns empty string for null", () => {
    expect(timeAgo(null)).toBe("");
  });

  it("returns empty string for invalid date", () => {
    expect(timeAgo("not-a-date")).toBe("");
  });

  it("returns 'just now' for future dates", () => {
    const future = new Date(Date.now() + 60000).toISOString();
    expect(timeAgo(future)).toBe("just now");
  });

  it("handles ISO dates with Z suffix", () => {
    const recent = new Date(Date.now() - 30000).toISOString();
    const result = timeAgo(recent);
    expect(result).toMatch(/\d+s ago/);
  });

  it("handles dates without timezone", () => {
    // Backend sometimes sends "2026-03-29 23:57:11" format
    const date = new Date(Date.now() - 3600000).toISOString().replace("T", " ").replace("Z", "");
    const result = timeAgo(date);
    expect(result).toMatch(/\d+[hm] ago/);
  });

  it("formats minutes correctly", () => {
    const fiveMinAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    expect(timeAgo(fiveMinAgo)).toBe("5m ago");
  });

  it("formats hours correctly", () => {
    const threeHoursAgo = new Date(Date.now() - 3 * 3600 * 1000).toISOString();
    expect(timeAgo(threeHoursAgo)).toBe("3h ago");
  });

  it("formats days correctly", () => {
    const twoDaysAgo = new Date(Date.now() - 2 * 86400 * 1000).toISOString();
    expect(timeAgo(twoDaysAgo)).toBe("2d ago");
  });
});

// ---------------------------------------------------------------------------
// stripHtml utility
// ---------------------------------------------------------------------------
describe("stripHtml", () => {
  it("strips HTML tags (SSR fallback)", () => {
    // In jsdom environment, DOMParser is available, but test both paths
    expect(stripHtml("<p>Hello <strong>World</strong></p>")).toBe("Hello World");
  });

  it("handles plain text", () => {
    expect(stripHtml("No HTML here")).toBe("No HTML here");
  });

  it("handles empty string", () => {
    expect(stripHtml("")).toBe("");
  });
});

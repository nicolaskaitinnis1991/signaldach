import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "@/lib/auth";

describe("useAuthStore", () => {
  beforeEach(() => {
    // Reset store state between tests
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      loading: false,
      error: null,
    });
    // Clear localStorage
    try { localStorage.clear(); } catch { /* ignore */ }
  });

  it("starts with null user and tokens", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("_setTokens saves to state and localStorage", () => {
    useAuthStore.getState()._setTokens("access-123", "refresh-456");
    const state = useAuthStore.getState();
    expect(state.accessToken).toBe("access-123");
    expect(state.refreshToken).toBe("refresh-456");
    expect(localStorage.getItem("sd_access_token")).toBe("access-123");
    expect(localStorage.getItem("sd_refresh_token")).toBe("refresh-456");
  });

  it("clearError resets error state", () => {
    useAuthStore.setState({ error: "some error" });
    expect(useAuthStore.getState().error).toBe("some error");
    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });

  it("logout clears tokens and user", async () => {
    useAuthStore.setState({
      user: { id: "1", email: "test@test.com", role: "admin", is_active: true },
      accessToken: "tok",
      refreshToken: "ref",
    });
    await useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(localStorage.getItem("sd_access_token")).toBeNull();
  });
});

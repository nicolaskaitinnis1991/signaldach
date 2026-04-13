"use client";

import { create } from "zustand";
import { BACKEND_URL } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface AuthUser {
  id: string;
  email: string;
  role: "admin" | "analyst" | "viewer";
  is_active: boolean;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  loading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<boolean>;
  fetchUser: () => Promise<void>;
  clearError: () => void;
  _setTokens: (access: string, refresh: string) => void;
}

// ---------------------------------------------------------------------------
// Token persistence (memory + localStorage fallback)
// ---------------------------------------------------------------------------
function loadTokens(): { access: string | null; refresh: string | null } {
  try {
    return {
      access: localStorage.getItem("sd_access_token"),
      refresh: localStorage.getItem("sd_refresh_token"),
    };
  } catch {
    return { access: null, refresh: null };
  }
}

function saveTokens(access: string, refresh: string) {
  try {
    localStorage.setItem("sd_access_token", access);
    localStorage.setItem("sd_refresh_token", refresh);
  } catch {
    // Safari private mode, SSR, etc.
  }
}

function clearTokens() {
  try {
    localStorage.removeItem("sd_access_token");
    localStorage.removeItem("sd_refresh_token");
  } catch {
    // ignore
  }
}

// ---------------------------------------------------------------------------
// Authenticated fetch helper
// ---------------------------------------------------------------------------
export async function authFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = useAuthStore.getState().accessToken;
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, { ...options, headers });
}

// ---------------------------------------------------------------------------
// Zustand Auth Store
// ---------------------------------------------------------------------------
const initialTokens = typeof window !== "undefined" ? loadTokens() : { access: null, refresh: null };

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: initialTokens.access,
  refreshToken: initialTokens.refresh,
  loading: false,
  error: null,

  _setTokens: (access, refresh) => {
    saveTokens(access, refresh);
    set({ accessToken: access, refreshToken: refresh });
  },

  clearError: () => set({ error: null }),

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`${BACKEND_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || `Login failed (${res.status})`);
      }
      const data = await res.json();
      get()._setTokens(data.access_token, data.refresh_token);

      // Fetch user profile
      await get().fetchUser();
      set({ loading: false });
    } catch (err) {
      set({ loading: false, error: (err as Error).message });
      throw err;
    }
  },

  logout: async () => {
    const token = get().accessToken;
    // Best-effort server-side logout
    try {
      if (token) {
        await fetch(`${BACKEND_URL}/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
      }
    } catch {
      // ignore
    }
    clearTokens();
    set({ user: null, accessToken: null, refreshToken: null, error: null });
  },

  refreshSession: async () => {
    const refresh = get().refreshToken;
    if (!refresh) return false;
    try {
      const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      get()._setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    }
  },

  fetchUser: async () => {
    const token = get().accessToken;
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const user = await res.json();
        set({ user });
      } else if (res.status === 401) {
        // Try refresh
        const refreshed = await get().refreshSession();
        if (refreshed) {
          await get().fetchUser();
        } else {
          clearTokens();
          set({ user: null, accessToken: null, refreshToken: null });
        }
      }
    } catch {
      // ignore network errors
    }
  },
}));

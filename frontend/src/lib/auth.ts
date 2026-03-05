import type { AuthUser } from "@/types";

const KEY = "sc_auth";

export function saveAuth(auth: AuthUser) {
  if (typeof window !== "undefined") {
    localStorage.setItem(KEY, JSON.stringify(auth));
  }
}

export function getAuth(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function clearAuth() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(KEY);
  }
}

export function getToken(): string | null {
  return getAuth()?.access_token ?? null;
}

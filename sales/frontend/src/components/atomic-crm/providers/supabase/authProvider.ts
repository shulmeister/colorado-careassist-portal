import type { AuthProvider } from "ra-core";

// Minimal auth provider that trusts the backend session (portal or cookie).
// We fetch /auth/me to get the user identity; fallback to a local placeholder
// so react-admin renders even in dev without OAuth.
const fetchIdentity = async () => {
  try {
    const res = await fetch("/auth/me", { credentials: "include" });
    if (res.ok) {
      const body = await res.json();
      const user = body?.user;
      if (user?.email) {
        return {
          id: user.email,
          fullName: user.name ?? user.email,
          email: user.email,
        };
      }
    }
  } catch (err) {
    console.warn("authProvider: falling back to local identity", err);
  }
  return { id: "dev-user", fullName: "Portal User" };
};

export const getIsInitialized = async () => true;

export const authProvider: AuthProvider = {
  login: async () => undefined,
  logout: async () => undefined,
  checkAuth: async () => undefined,
  checkError: async () => undefined,
  getPermissions: async () => undefined,
  canAccess: async () => true,
  getIdentity: async () => fetchIdentity(),
};

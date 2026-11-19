import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { TokenResponse, UserRole } from "@/types/taskmesh";

interface AuthState {
  token: string | null;
  role: UserRole | null;
  tenant: string | null;
  subject: string | null;
  expiresAt: number | null;
  setSession: (session: TokenResponse) => void;
  signOut: () => void;
  isAuthenticated: () => boolean;
}

const EMPTY = {
  token: null,
  role: null,
  tenant: null,
  subject: null,
  expiresAt: null
} as const;

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      ...EMPTY,
      setSession: (session) =>
        set({
          token: session.access_token,
          role: session.role,
          tenant: session.tenant,
          subject: session.subject,
          expiresAt: session.expires_at
        }),
      signOut: () => set({ ...EMPTY }),
      isAuthenticated: () => {
        const { token, expiresAt } = get();
        if (!token) {
          return false;
        }
        // Treat a token that expires within 30 seconds as already expired.
        return expiresAt === null || expiresAt - 30 > Date.now() / 1000;
      }
    }),
    { name: "taskmesh-auth" }
  )
);

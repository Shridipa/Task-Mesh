import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserRole } from "@/types/taskmesh";

interface AuthState {
  role: UserRole;
  setRole: (role: UserRole) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      role: "admin",
      setRole: (role) => set({ role }),
      logout: () => set({ role: "viewer" })
    }),
    { name: "taskmesh-auth" }
  )
);

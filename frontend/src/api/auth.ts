import type { UserRole } from "@/types/taskmesh";

export const supportedRoles: UserRole[] = ["admin", "developer", "viewer"];

// TODO: Backend endpoint required for JWT login, refresh tokens, and user identity.
export function getRoleCapabilities(role: UserRole): string[] {
  if (role === "admin") {
    return ["Read", "Write", "Replay DLQ", "Delete jobs"];
  }
  if (role === "developer") {
    return ["Read", "Write"];
  }
  return ["Read"];
}

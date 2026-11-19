import { apiClient } from "@/api/client";
import type { TokenResponse, UserRole } from "@/types/taskmesh";

export const supportedRoles: UserRole[] = ["admin", "developer", "viewer"];

/**
 * Exchange an API key for a short-lived access token.
 *
 * The key is only ever sent to this endpoint; every other request carries the
 * signed token, and the role in it is decided by the backend.
 */
export async function requestToken(apiKey: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/auth/token", { api_key: apiKey });
  return data;
}

export function getRoleCapabilities(role: UserRole): string[] {
  if (role === "admin") {
    return ["Read", "Write", "Replay DLQ", "Delete jobs", "Scheduler control"];
  }
  if (role === "developer") {
    return ["Read", "Write"];
  }
  return ["Read"];
}

import axios, { AxiosError } from "axios";
import { useAuthStore } from "@/store/auth-store";
import type { ApiError } from "@/types/taskmesh";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  timeout: 15_000
});

apiClient.interceptors.request.use((config) => {
  const { token, isAuthenticated } = useAuthStore.getState();
  if (token && isAuthenticated()) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail;
    const isTokenRequest = error.config?.url?.startsWith("/auth/token");
    if (status === 401 && !isTokenRequest) {
      // The session is no longer valid; drop it so the UI can ask for a key.
      useAuthStore.getState().signOut();
    }
    const message =
      typeof detail === "string" && detail.length > 0 ? detail : error.message ?? "Request failed";
    return Promise.reject({ status, message } satisfies ApiError);
  }
);

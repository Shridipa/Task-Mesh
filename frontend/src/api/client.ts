import axios, { AxiosError } from "axios";
import { useAuthStore } from "@/store/auth-store";
import type { ApiError } from "@/types/taskmesh";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api",
  timeout: 15_000
});

apiClient.interceptors.request.use((config) => {
  config.headers.set("X-Role", useAuthStore.getState().role);
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const message = error.response?.data?.detail ?? error.message ?? "Request failed";
    return Promise.reject({ status, message } satisfies ApiError);
  }
);

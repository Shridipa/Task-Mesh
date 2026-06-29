import { apiClient } from "@/api/client";

export async function getSchedulerStatus() {
  const { data } = await apiClient.get("/scheduler/status");
  return data;
}

export async function pauseScheduler() {
  const { data } = await apiClient.post("/scheduler/pause");
  return data;
}

export async function resumeScheduler() {
  const { data } = await apiClient.post("/scheduler/resume");
  return data;
}

export async function runSchedulerNow() {
  const { data } = await apiClient.post("/scheduler/run-now");
  return data;
}
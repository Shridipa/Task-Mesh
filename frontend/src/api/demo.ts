import { apiClient } from "@/api/client";

export async function generateDemoWorkers(count = 3) {
  const { data } = await apiClient.post("/demo/generate-workers", null, { params: { count } });
  return data;
}

export async function generateDemoJobs(count = 10) {
  const { data } = await apiClient.post("/demo/generate-jobs", null, { params: { count } });
  return data;
}

export async function resetDemo() {
  const { data } = await apiClient.post("/demo/reset");
  return data;
}
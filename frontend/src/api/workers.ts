import { apiClient } from "@/api/client";
import type { Worker } from "@/types/taskmesh";

export async function listWorkers(active = false): Promise<Worker[]> {
  const { data } = await apiClient.get<Worker[]>("/workers/", { params: { active } });
  return data;
}

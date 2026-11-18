import { apiClient } from "@/api/client";
import type { TextJob } from "@/types/taskmesh";

export async function submitTextJob(text: string): Promise<TextJob> {
  const { data } = await apiClient.post<TextJob>("/text/jobs", { text });
  return data;
}

export async function getTextJob(jobId: string): Promise<TextJob> {
  const { data } = await apiClient.get<TextJob>(`/text/jobs/${jobId}`);
  return data;
}

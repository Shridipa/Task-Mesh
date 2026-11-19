import { apiClient } from "@/api/client";
import type { AnalysisJob, AnalysisTask } from "@/types/taskmesh";

export async function submitAnalysisJob(task: AnalysisTask, content: string): Promise<AnalysisJob> {
  const { data } = await apiClient.post<AnalysisJob>("/analysis/jobs", { task, content });
  return data;
}

export async function getAnalysisJob(jobId: string): Promise<AnalysisJob> {
  const { data } = await apiClient.get<AnalysisJob>(`/analysis/jobs/${jobId}`);
  return data;
}

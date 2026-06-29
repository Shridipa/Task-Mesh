import { apiClient } from "@/api/client";
import type { Job, JobCreateInput } from "@/types/taskmesh";

export interface JobListParams {
  status?: string;
  tenant_id?: string;
  limit?: number;
  offset?: number;
}

export async function listJobs(params: JobListParams = {}): Promise<Job[]> {
  const { data } = await apiClient.get<Job[]>("/jobs/", { params });
  return data;
}

export async function getJob(jobId: string): Promise<Job> {
  const { data } = await apiClient.get<Job>(`/jobs/${jobId}`);
  return data;
}

export async function createJob(input: JobCreateInput): Promise<Job> {
  const { data } = await apiClient.post<Job>("/jobs/", input);
  return data;
}

export async function replayJob(jobId: string): Promise<Job> {
  const { data } = await apiClient.post<Job>(`/jobs/${jobId}/replay`);
  return data;
}

export async function cancelJob(jobId: string): Promise<Job> {
  const { data } = await apiClient.post<Job>(`/jobs/${jobId}/cancel`);
  return data;
}

export async function duplicateJob(jobId: string): Promise<Job> {
  const { data } = await apiClient.post<Job>(`/jobs/${jobId}/duplicate`);
  return data;
}

export async function deleteJob(jobId: string): Promise<void> {
  await apiClient.delete(`/jobs/${jobId}`);
}

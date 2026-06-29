import { apiClient } from "@/api/client";

export interface LogEntry {
  timestamp: string;
  level: string;
  source: string;
  job_id?: string;
  message: string;
  event_type?: string;
}

export async function getLogs(limit = 200, offset = 0, eventType?: string, jobId?: string): Promise<LogEntry[]> {
  const { data } = await apiClient.get<LogEntry[]>("/logs/", {
    params: { limit, offset, event_type: eventType, job_id: jobId },
  });
  return data;
}
import { apiClient } from "@/api/client";
import type { Event } from "@/types/taskmesh";

export async function listEvents(params?: {
  job_id?: string;
  tenant_id?: string;
  event_type?: string;
  limit?: number;
  offset?: number;
}): Promise<Event[]> {
  const { data } = await apiClient.get<Event[]>("/events/", { params });
  return data;
}
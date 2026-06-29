import { apiClient } from "@/api/client";
import type { Metrics } from "@/types/taskmesh";

export async function getDashboardMetrics(): Promise<Metrics> {
  const { data } = await apiClient.get<Metrics>("/dashboard/metrics");
  return data;
}

export async function getMetricsSummary(): Promise<Metrics> {
  const { data } = await apiClient.get<Metrics>("/metrics/summary");
  return data;
}

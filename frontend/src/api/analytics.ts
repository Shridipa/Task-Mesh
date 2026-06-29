import { apiClient } from "@/api/client";

export async function getAnalyticsTimeSeries(hours = 24) {
  const { data } = await apiClient.get("/analytics/time-series", { params: { hours } });
  return data;
}
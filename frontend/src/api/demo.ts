import { apiClient } from "@/api/client";

export interface LiveDemoSubmission {
  created: Array<{ id: string; status: string }>;
  message: string;
}

export async function runLiveDemo(count = 1): Promise<LiveDemoSubmission> {
  const { data } = await apiClient.post<LiveDemoSubmission>("/demo/run", null, {
    params: { count }
  });
  return data;
}

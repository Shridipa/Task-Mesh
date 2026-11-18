export type UserRole = "admin" | "developer" | "viewer";

export type JobStatus =
  | "pending"
  | "scheduled"
  | "running"
  | "completed"
  | "failed"
  | "dead_letter"
  | "canceled";

export interface Job {
  id: string;
  job_type: string;
  payload: Record<string, unknown>;
  tenant_id: string;
  priority: number;
  status: JobStatus;
  retry_count: number;
  max_retries: number;
  failure_reason: string | null;
  result: Record<string, unknown> | null;
  idempotency_key: string | null;
  created_at: string;
  execute_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  worker_id: string | null;
  history: string[];
}

export interface TextProcessResult {
  words: number;
  characters: number;
  sentences: number;
  lines: number;
  cleaned_text: string;
}

export type TextJob = Omit<Job, "result"> & { result: TextProcessResult | null };

export interface JobCreateInput {
  job_type: string;
  payload: Record<string, unknown>;
  priority: number;
  tenant_id: string;
  execute_at?: string | null;
  max_retries: number;
  idempotency_key?: string | null;
}

export interface Worker {
  id: string;
  hostname: string;
  cpu_usage: number;
  memory_usage: number;
  active_jobs: number;
  status: string;
  last_heartbeat: string;
}

export interface Metrics {
  pending: number;
  scheduled: number;
  running: number;
  completed: number;
  failed: number;
  dead_letter: number;
  active_workers: number;
  throughput_per_minute: number;
  retry_rate: number;
}

export interface Event {
  id: string;
  event_type: string;
  job_id: string | null;
  tenant_id: string;
  message: string;
  created_at: string;
}

export interface ApiError {
  status?: number;
  message: string;
}

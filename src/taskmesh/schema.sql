CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY,
  status TEXT NOT NULL,
  job_type TEXT NOT NULL,
  priority INTEGER NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 5,
  tenant_id TEXT NOT NULL,
  idempotency_key TEXT,
  failure_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status_priority
  ON jobs (tenant_id, status, priority DESC, created_at ASC);

CREATE TABLE IF NOT EXISTS workers (
  id TEXT PRIMARY KEY,
  hostname TEXT NOT NULL,
  cpu_usage NUMERIC NOT NULL,
  memory_usage NUMERIC NOT NULL,
  status TEXT NOT NULL,
  last_heartbeat TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY,
  event_type TEXT NOT NULL,
  job_id UUID REFERENCES jobs(id),
  tenant_id TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY,
  actor_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  action TEXT NOT NULL,
  target_id TEXT,
  created_at TIMESTAMPTZ NOT NULL
);


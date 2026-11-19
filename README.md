# TaskMesh

TaskMesh is a background task processing platform. Instead of making a user wait
while work is performed inside the request, it stores the work as a **job** in a
queue and lets **background workers** execute it independently.

The repository ships one working workload — **text processing** — so you can see
the whole pipeline move: submit → queue → worker → result → stored → displayed.

---

## 1. What TaskMesh does

- Accepts a task from a user and stores it as a job with a status.
- Hands that job to a background worker when one is free.
- Lets the worker execute the task and save the output.
- Retries failed jobs with exponential backoff, and moves exhausted jobs to a
  dead-letter queue.
- Shows the real state of every job, worker and queue in a web console.

## 2. Why background processing is useful

Sending email, generating reports, processing uploads or cleaning up data should
never block a page request. A queue decouples "accept the work" from "do the
work", so the API answers in milliseconds while a worker does the slow part. It
also gives you retries, scheduling, and an audit trail for free.

## 3. How the system works

```
Visitor
  │  POST /text/jobs  { "text": "..." }
  ▼
FastAPI API ──────────► creates a job (status = pending) in the database
  │
  ▼
Scheduler (1s loop) ──► promotes scheduled jobs whose time has come
  │
  ▼
Worker (poll loop) ───► leases the job (status = running, worker_id, started_at)
  │
  ▼
text.process handler ─► computes word/character/sentence/line counts + cleaned text
  │
  ▼
Engine ───────────────► stores result JSON, status = completed, completed_at
  │
  ▼
GET /text/jobs/{id} ──► the console polls until the job is finished, then shows
                        the stored result
```

Nothing is simulated: the numbers come from the worker's handler, and they are
read back from the database afterwards.

## 4. The text-processing demo

`text.process` computes these values **from the cleaned text**:

| Value | Rule |
| --- | --- |
| Words | whitespace-separated tokens |
| Characters | every character of the cleaned text, spaces and newlines included |
| Sentences | segments separated by `.`, `!` or `?` (empty segments ignored, so trailing punctuation does not add a sentence) |
| Lines | lines separated by `\n` |

Cleaning: `\r\n`/`\r` become `\n`, runs of spaces/tabs collapse to one space,
each line is trimmed, runs of 3+ newlines collapse to one blank line, and the
whole text is trimmed. Input must be 1–10,000 characters and is only ever
processed as text — never executed as code.

Counting is deterministic: the same input always produces the same result.

## 5. API

Public demo routes (no credentials, per-client rate limited):

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/text/jobs` | Submit `{"text": "..."}`; returns the created job |
| `GET` | `/text/jobs/{job_id}` | Status of that text job, including `result` once completed |

Administrative and monitoring routes (header-based roles):

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe |
| `GET` | `/dashboard/metrics` | Job counts, active workers, retry rate |
| `POST` | `/jobs/` | Create a job (admin/developer) |
| `GET` | `/jobs/` | List jobs, filter by `status`/`tenant_id` (any role) |
| `GET` | `/jobs/{id}` | Read one job (any role) |
| `POST` | `/jobs/{id}/lease` | Worker leases a job |
| `POST` | `/jobs/{id}/complete` | Worker marks a job done |
| `POST` | `/jobs/{id}/fail` | Worker reports a failure (retry/DLQ) |
| `POST` | `/jobs/{id}/replay` | Replay a dead-letter job (admin) |
| `POST` | `/jobs/{id}/cancel` | Cancel a pending job (admin) |
| `GET` | `/workers/` | Registered workers |
| `GET` | `/events/` | Job lifecycle events |
| `GET` | `/metrics/summary` | Metrics as JSON |
| `GET` | `/metrics/prometheus` | Prometheus exposition format |
| `GET`/`POST` | `/scheduler/*` | Scheduler status, pause/resume, run-now |
| `GET` | `/analytics/timeseries` | Hourly job counts |

Access is self-asserted through headers (`X-Role: admin|developer|viewer`), and
worker-only routes additionally require `X-Worker-Token`. The public `/text`
routes need no header so a visitor can try the demo. Interactive docs live at
`/docs`.

## 6. What the scheduler does

`src/taskmesh/scheduler.py` runs every second. It promotes `scheduled` jobs whose
`execute_at` has passed to `pending`, and marks workers inactive when their
heartbeat is older than a minute. With Redis available it takes a distributed
lock (`scheduler_lock`, `SET NX EX 5`) so only one scheduler acts at a time;
without Redis it runs in single-process mode.

## 7. What a worker does

`src/taskmesh/worker.py` sends a heartbeat (so it appears in the console), then
leases the highest-priority pending job, runs the handler registered for its job
type (`src/taskmesh/tasks.py`), and stores either the result
(`engine.complete_job(job_id, result)`) or the error (`engine.fail_job`). Failures
are retried with backoff `min(2**retry_count, 300)` seconds up to `max_retries`,
then dead-lettered. A job type with no handler fails with
`no handler is registered for job type '...'`.

The API process starts a scheduler and a worker in its lifespan, so a single
`uvicorn` process is already a working system. You can also run a worker as its
own process to add capacity.

## 8. Running the backend

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

uvicorn taskmesh.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health: `curl http://localhost:8000/health`

With no `DATABASE_URL` the app uses SQLite (`./test.db`) and creates its tables
on startup. Alembic migrations live in `alembic/` (`alembic upgrade head`).

## 9. Running an extra worker

```bash
source .venv/bin/activate
python -m taskmesh.worker
```

Set `WORKER_ID` to give it a readable name. Workers need the same
`DATABASE_URL` as the API.

## 10. Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `http://127.0.0.1:8000`, so
keep the backend running. Use `VITE_API_BASE_URL` to point at a different API.

## 11. Required environment variables and services

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite+aiosqlite:///./test.db` | `postgresql+asyncpg://user:pass@host/db` for PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional: distributed scheduler lock and rate limiting |
| `WORKER_SECRET` | `taskmesh_secret` | Token for worker-only routes — change it in production |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `WORKER_ID` | hostname | Name shown for the worker |
| `VITE_API_BASE_URL` | `/api` | Frontend API base URL |

Redis is optional; without it the scheduler runs without the distributed lock
and the rate limiter allows requests. PostgreSQL is optional; the demo runs on
SQLite out of the box. `docker-compose.yml` provides API, Redis, PostgreSQL,
Prometheus and Grafana if you want the full stack.

## 12. Submitting a text-processing task

From the website: open the dashboard, paste text into **Try TaskMesh Yourself**
and press **Submit task**. The panel shows the real job ID, the real status
changes and the worker's result. The page URL records the job id
(`/?job=<job-id>`), so refreshing — or opening that link again — fetches the
stored job and result from the API.

From the command line:

```bash
curl -s -X POST http://localhost:8000/text/jobs \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello world. TaskMesh runs this in the background!"}'

# → {"id":"<job-id>","job_type":"text.process","status":"pending", ...}
```

## 13. Verifying that the worker actually executed it

```bash
curl -s http://localhost:8000/text/jobs/<job-id>
```

A finished job looks like this — `worker_id`, both timestamps and `result` are
written by the worker, not by the API:

```json
{
  "id": "<job-id>",
  "job_type": "text.process",
  "status": "completed",
  "worker_id": "your-hostname",
  "created_at": "2024-06-26T10:00:00Z",
  "started_at": "2024-06-26T10:00:01Z",
  "completed_at": "2024-06-26T10:00:01Z",
  "result": {
    "words": 8,
    "characters": 50,
    "sentences": 2,
    "lines": 1,
    "cleaned_text": "Hello world. TaskMesh runs this in the background!"
  }
}
```

The same data is visible in the console under **Jobs** (and the lifecycle events
under **Events**). You can also inspect the database directly:

```bash
sqlite3 test.db "select id, status, worker_id, result from jobs order by created_at desc limit 5;"
```

If no worker is running, the job honestly stays `pending` — the console shows
"Waiting in queue" with no invented progress.

## 14. Tests

```bash
pip install -e ".[dev]"
pytest                                  # backend, includes the end-to-end worker test
ruff check .                            # lint

cd frontend
npm run lint
npm run build                           # TypeScript + production build
npm test                                # component tests
```

`tests/test_text_demo.py` covers the counting rules (including Unicode and
whitespace normalization), input validation, result persistence, the retry path
and a real submit → worker → completed → read-back cycle.
`frontend/src/features/text/TextDemo.test.tsx` covers the form validation, the
real job id and statuses, the rendered result, API errors, URL/storage restore
and that polling stops once the job is finished.

## 15. Project layout

```
src/taskmesh/
  text_processing.py     the demo workload (counting rules)
  tasks.py               job_type → handler dispatch used by workers
  worker.py              heartbeat, lease, execute, complete/fail
  scheduler.py           due-job promotion, worker expiry, Redis lock
  engine.py              single source of truth for jobs, workers, events
  db/models.py           SQLAlchemy ORM (jobs include a nullable result JSON)
  api/routes/text.py     public submission + status endpoints
  api/routes/*.py        jobs, workers, metrics, events, logs, analytics, scheduler
frontend/src/
  pages/OverviewPage.tsx        explanation, live stats, flow, demo
  features/text/TextDemo.tsx    submission form, lifecycle, result
alembic/versions/              schema migrations (latest: job result column)
```

## 16. Known limitations

- Access control is header-based (`X-Role`), not authenticated users — see the
  TODO in `src/taskmesh/api/auth.py`.
- When `DATABASE_URL` points at PostgreSQL the API currently falls back to a
  local SQLite file, so the one-day demo runs on SQLite. Redis is optional.
- Only `text.process` has a handler. Any other job type fails honestly through
  the retry/dead-letter path instead of pretending to succeed.

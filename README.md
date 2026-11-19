# TaskMesh

TaskMesh is a background task processing platform. Instead of making a user wait
while work is performed inside the request, it stores the work as a **job** in a
queue and lets **background workers** execute it independently.

The repository ships three working workloads — **text processing**, **JSON
validation** and **CSV analysis** — so you can see the whole pipeline move:
submit → queue → worker → result → stored → displayed.

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

## 4. The demo workloads

All three workloads use the same pipeline and differ only in the handler the
worker runs.

### 4.1 Text processing (`text.process`)

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

### 4.2 JSON validation (`json.validate`)

`json.validate` parses the document with Python's strict JSON decoder (`NaN`
and `Infinity` are rejected because they are not valid JSON) and returns:

| Value | Rule |
| --- | --- |
| `formatted` | the document re-serialised with 2-space indentation |
| `root_type` | `object`, `array`, `string`, `number`, `boolean` or `null` |
| `counts` | objects, arrays, keys, strings, numbers, booleans and nulls found anywhere in the document |
| `max_depth` | nesting depth of the deepest value |
| `size` | length of the submitted document |

Invalid JSON (a syntax error, single quotes, a trailing comma, missing braces
or brackets, `NaN`, …) is a permanent failure: the job ends as `failed` with a
reason such as `Invalid JSON at line 4, column 1: Expecting property name
enclosed in double quotes`. It is not retried and never reported as completed.
Input must be 1–100,000 characters and Unicode is preserved.

### 4.3 CSV analysis (`csv.analyze`)

`csv.analyze` reads the document with Python's strict CSV reader, so quoted
values, commas inside quotes, doubled quotes (`""`) and newlines inside quoted
fields all behave like a spreadsheet export. The first row is the header.

| Value | Rule |
| --- | --- |
| `rows`, `columns` | data rows (header excluded) and column count |
| `column_names` | trimmed header names; blank names become `column_N`, duplicates get a `_2` suffix |
| `missing_values` | empty or whitespace-only cells, per column and in total |
| `numeric_columns`, `statistics` | columns whose every non-missing value parses as a number, with count, mean, median, min and max |
| `duplicate_rows` | data rows identical to an earlier row |
| `ragged_rows` | rows whose field count differs from the header (short rows are padded, extra fields are kept and reported) |
| `preview` | the first five rows as objects |

Unparseable documents (for example an unterminated quoted field) fail the job
permanently with `Invalid CSV: …`. Input must be 1–200,000 characters. A header
without data rows is a valid, empty table.

## 5. API

Public demo routes (no credentials, per-client rate limited):

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/text/jobs` | Submit `{"text": "..."}`; returns the created job |
| `GET` | `/text/jobs/{job_id}` | Status of that text job, including `result` once completed |
| `POST` | `/analysis/jobs` | Submit `{"task": "json.validate"}` or `{"task": "csv.analyze"}` with the document in `content` |
| `GET` | `/analysis/jobs/{job_id}` | Status of that analysis job, including `result` once completed |

Administrative and monitoring routes (signed-in tokens, see §6):

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
| `POST` | `/auth/token` | Exchange an API key for a short-lived access token |
| `GET` | `/auth/me` | Identity, role and tenant of the current token |
| `GET` | `/ready` | Readiness probe (database and Redis status) |

The public `/text` and `/analysis` routes need no credentials so a visitor can
try the live demos; everything else requires a token. Interactive docs live at
`/docs` and the OpenAPI schema at `/openapi.json`.

## 6. Authentication and authorization

The API never trusts a client-supplied role. Access works like this:

1. An operator configures long-lived API keys in `AUTH_API_KEYS`, as
   `key:role:tenant` triples (`admin`, `developer` or `viewer`).
2. The frontend (or a script) posts a key to `POST /auth/token` and receives a
   short-lived HS256 JWT signed with `AUTH_JWT_SECRET`, plus its role, tenant and
   expiry. Keys are compared in constant time.
3. Every protected request carries `Authorization: Bearer <token>`. The token's
   signature, `exp`, `iss` and `aud` are verified before the role or tenant is
   used. A tampered or expired token is rejected with `401`.

Roles are enforced per route: reads need `viewer` or better, writes need
`developer` or better, administration (replay, cancel, delete, worker
maintenance, scheduler control) needs `admin`. `developer` and `viewer` tokens
are scoped to their own tenant: they see and create jobs for that tenant only,
and asking for another job id returns `404` rather than `403`, so ids cannot be
probed.

```bash
curl -s -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"api_key":"<your key>"}'
# {"access_token":"<jwt>","token_type":"bearer","role":"developer","tenant":"acme","expires_in":3600}

curl -s http://localhost:8000/jobs/ -H "Authorization: Bearer <jwt>"
```

Workers are not users. They present `X-Worker-Token: $WORKER_SECRET` (compared in
constant time) and their `X-Worker-Id` when they lease, heartbeat, complete or
fail a job. Worker routes are not reachable with a user token.

`/health` is always public. `/metrics/prometheus` is public only when
`METRICS_PUBLIC=true`, which is intended for a Prometheus scraper on an internal
network; with the default Compose stack the API port is not published at all.

## 7. CORS, request limits and rate limiting

- `CORS_ORIGINS` is a comma-separated allowlist. In production a wildcard is
  rejected at startup: the app refuses to boot with `CORS_ORIGINS=*`.
- Request bodies are capped at `MAX_REQUEST_BYTES` (default 2 MiB) and oversized
  requests get `413` before they are parsed. Each workload additionally enforces
  its own character limit.
- The public demo routes share a per-client sliding-window limiter
  (`RATE_LIMIT_SUBMISSIONS` per `RATE_LIMIT_WINDOW_SECONDS`, keyed by
  `X-Forwarded-For` when present). Exceeding it returns `429`. The limiter is
  in-process and bounded in memory: run one API replica, or move the limiter to
  Redis, if you scale out.
- Unhandled errors return a generic `500` with a request id; the traceback is
  logged, never returned.
- Responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer` and `Cache-Control: no-store`; every request is
  tagged with `X-Request-Id`, which is also included in error responses so a
  user-facing failure can be matched to a server log line.

## 8. What the scheduler does

`src/taskmesh/scheduler.py` runs every second. It promotes `scheduled` jobs whose
`execute_at` has passed to `pending`, and marks workers inactive when their
heartbeat is older than a minute. With Redis available it takes a distributed
lock (`scheduler_lock`, `SET NX EX 5`) so only one scheduler acts at a time;
without Redis it runs in single-process mode.

## 9. What a worker does

`src/taskmesh/worker.py` sends a heartbeat (so it appears in the console), then
leases the highest-priority pending job, runs the handler registered for its job
type (`src/taskmesh/tasks.py`), and stores either the result
(`engine.complete_job(job_id, result)`) or the error (`engine.fail_job`). Failures
are retried with backoff `min(2**retry_count, 300)` seconds up to `max_retries`,
then dead-lettered. A job type with no handler fails with
`no handler is registered for job type '...'`.

Payload errors (`JobInputError`: empty input, invalid JSON, unparseable CSV) skip
the retry path — `engine.fail_job(..., retryable=False)` marks the job `failed`
immediately, because retrying identical input cannot succeed.

The API process starts a scheduler and a worker in its lifespan, so a single
`uvicorn` process is already a working system. You can also run a worker as its
own process to add capacity.

## 10. Running the backend

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
on startup. For PostgreSQL, set the URL and apply the migrations once:

```bash
export DATABASE_URL='postgresql+asyncpg://taskmesh:secret@localhost:5432/taskmesh'
alembic upgrade head      # PostgreSQL only: Alembic refuses to run against SQLite
alembic check             # fails if the models and migrations have drifted apart
```

Migrations are the supported way to create a PostgreSQL schema; automatic table
creation (`AUTO_CREATE_SCHEMA`) is for development and tests only and is refused
in production.

## 11. Running an extra worker

```bash
source .venv/bin/activate
python -m taskmesh.worker
```

Set `WORKER_ID` to give it a readable name. Workers need the same
`DATABASE_URL` as the API.

## 12. Running the frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to `http://127.0.0.1:8000`, so
keep the backend running. Use `VITE_API_BASE_URL` to point at a different API.

## 13. Required environment variables and services

| Variable | Default | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `production` enables strict validation (see below) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./test.db` | Used verbatim. `postgresql+asyncpg://user:pass@host/db` for PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Optional: scheduler lock and live log fan-out |
| `AUTH_JWT_SECRET` | dev-only default | Signs access tokens; 32+ characters, required in production |
| `AUTH_API_KEYS` | dev keys in development | `key:role:tenant,...` — the only way to obtain a token |
| `WORKER_SECRET` | required | Shared secret for worker-only routes |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated allowlist; `*` is refused in production |
| `RATE_LIMIT_SUBMISSIONS` / `RATE_LIMIT_WINDOW_SECONDS` | `10` / `60` | Public demo limiter |
| `MAX_REQUEST_BYTES` | `2097152` | Body size cap |
| `METRICS_PUBLIC` | `false` | Serve `/metrics/prometheus` without a token |
| `LOG_FORMAT` / `LOG_LEVEL` | `text` / `INFO` | `json` for container logs |
| `WORKER_ID` | hostname | Name shown for the worker |
| `VITE_API_BASE_URL` | `/api` | Frontend API base URL |

`.env.example` documents every variable with the production values.

**Production strictness.** When `ENVIRONMENT=production` the process refuses to
start if `AUTH_JWT_SECRET` is shorter than 32 characters or still a development
default, if `WORKER_SECRET` is missing, if `CORS_ORIGINS` is empty or `*`, or if
`AUTO_CREATE_SCHEMA=true`. There is no development API key in production, so
`AUTH_API_KEYS` must be set. Database URLs are never rewritten: a PostgreSQL URL
is used as PostgreSQL.

Redis is optional; without it the scheduler runs without the distributed lock
and log fan-out degrades to no-op. PostgreSQL is optional for the demo but is
what the Compose stack and the migration path use.

## 14. Submitting a text-processing task

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

The analysis tasks use the same flow:

```bash
curl -s -X POST http://localhost:8000/analysis/jobs \
  -H 'Content-Type: application/json' \
  -d '{"task":"json.validate","content":"{\"name\":\"TaskMesh\"}"}'

curl -s -X POST http://localhost:8000/analysis/jobs \
  -H 'Content-Type: application/json' \
  -d '{"task":"csv.analyze","content":"name,score\nAda,90\nGrace,80"}'

curl -s http://localhost:8000/analysis/jobs/<job-id>
```

## 15. Verifying that the worker actually executed it

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

## 16. Docker Compose deployment

The Compose stack runs PostgreSQL, Redis, the API, a separate worker, the
scheduler, the built React frontend behind nginx, Prometheus and Grafana. Only
the frontend port (`FRONTEND_PORT`, default 8080) is published; PostgreSQL,
Redis and the API stay on the internal network.

```bash
cp .env.example .env                 # then replace every CHANGE_ME value
docker compose build
docker compose up -d
docker compose ps                    # every service should be healthy
```

Then, once:

```bash
docker compose exec api alembic upgrade head
```

- Console: http://localhost:8080 — pick an API key from `AUTH_API_KEYS` and
  sign in under Settings to see the management pages.
- API (inside the network): `http://api:8000`, health at `/health`, readiness
  (database + Redis) at `/ready`.
- Grafana: `http://localhost:3000` when uncommented in `docker-compose.yml`.

Health checks are real: the API container reports `/ready`, the worker and
scheduler containers run `python -m taskmesh.liveness`, which fails when the
process stops refreshing its liveness file, so a wedged worker is restarted
instead of looking idle-and-healthy. PostgreSQL uses `pg_isready`, and Redis
uses `redis-cli ping`.

Logs: `docker compose logs -f api worker`. Set `LOG_FORMAT=json` (the default in
Compose) for one JSON object per line, including the job id, task type and
duration where relevant.

Upgrade and rollback:

```bash
docker compose pull && docker compose build
docker compose exec api alembic upgrade head
docker compose up -d --no-deps api worker scheduler frontend
```

Data lives in the `pgdata` volume and survives `docker compose down`. Never run
`docker compose down -v` unless you intend to delete the database. For backups:

```bash
docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > taskmesh-$(date +%F).sql
```

Shut down gracefully with `docker compose down`; the API, worker and scheduler
handle `SIGTERM` and finish the job they are holding.

**Before exposing this to the internet:** set real values for
`POSTGRES_PASSWORD`, `AUTH_JWT_SECRET` (32+ random characters), `WORKER_SECRET`,
`AUTH_API_KEYS` and `GF_SECURITY_ADMIN_PASSWORD`; set `CORS_ORIGINS` to your
frontend origin; keep `METRICS_PUBLIC=false` unless a scraper needs it; put
TLS and a reverse proxy in front of the frontend; and make sure the API port is
not published. `docker compose config` fails fast when a required value is
missing.

## 17. Tests

```bash
pip install -e ".[dev]"
pytest --cov=taskmesh --cov-report=term # 122 tests on SQLite, 87% coverage
ruff check .                            # lint

# The same suite against a real PostgreSQL (migrations are exercised too)
export TEST_DATABASE_URL='postgresql+asyncpg://taskmesh:secret@localhost:5432/taskmesh'
alembic upgrade head && alembic check
pytest                                  # 128 tests

cd frontend
npm test -- --run                       # component tests
npm run lint
npx tsc -b --noEmit
npm run build                           # production build
```

The suite runs without Redis: the limiter, scheduler lock and log fan-out use
in-process fallbacks, and the Redis code paths are covered by unit tests.

`tests/test_text_demo.py` covers the counting rules (including Unicode and
whitespace normalization), input validation, result persistence, the retry path
and a real submit → worker → completed → read-back cycle.
`frontend/src/features/text/TextDemo.test.tsx` covers the form validation, the
real job id and statuses, the rendered result, API errors, URL/storage restore
and that polling stops once the job is finished.

`tests/test_analysis_tasks.py` covers the JSON and CSV rules (root types,
Unicode, invalid documents with line and column, quoted CSV fields, missing
values, duplicates, statistics), dispatch for all three job types, the public
analysis API, and real submit → worker → completed runs for both workloads.
`frontend/src/features/analysis/AnalysisDemo.test.tsx` covers the analysis form,
both result panels, the failure state and URL restore.

## 18. Project layout

```
src/taskmesh/
  text_processing.py     text.process workload (counting rules)
  json_validation.py     json.validate workload (structure + formatted output)
  csv_analysis.py        csv.analyze workload (shape, missing values, statistics)
  errors.py              JobInputError: deterministic payload failures
  tasks.py               job_type → handler dispatch used by workers
  worker.py              heartbeat, lease, execute, complete/fail
  scheduler.py           due-job promotion, worker expiry, Redis lock
  engine.py              single source of truth for jobs, workers, events
  db/models.py           SQLAlchemy ORM (jobs include a nullable result JSON)
  api/routes/text.py     public text submission + status endpoints
  api/routes/analysis.py public JSON/CSV submission + status endpoints
  api/auth.py            token issuing/verification, roles, tenant scoping
  api/routes/auth.py     POST /auth/token, GET /auth/me
  config.py              environment parsing, production validation, URL redaction
  logging_config.py      JSON/text logs with request and job context
  liveness.py            worker/scheduler liveness files used by healthchecks
  api/routes/*.py        jobs, workers, metrics, events, logs, analytics, scheduler
frontend/src/
  pages/OverviewPage.tsx        explanation, live stats, flow, demo
  features/text/TextDemo.tsx    text form, lifecycle, result
  features/analysis/AnalysisDemo.tsx  JSON/CSV form and result panels
alembic/versions/              schema migrations (latest: schema matches models)
```

## 19. Known limitations

- The public demo routes (`/text/jobs`, `/analysis/jobs` and their status
  endpoints) are intentionally unauthenticated and rate limited per client. The
  limiter is per-process, so behind several API replicas each replica enforces
  its own budget.
- Job execution is at-least-once, not exactly-once. A worker whose lease expires
  while it is still running can lose the job; the engine rejects a completion
  from a worker that no longer owns it, but a handler with external side effects
  could still run twice.
- Handlers are CPU-light and run inside the worker process. There is no per-job
  timeout, so a pathological document could occupy a worker for a while.
- Three job types have handlers: `text.process`, `json.validate` and
  `csv.analyze`. Any other job type fails honestly through the retry/dead-letter
  path instead of pretending to succeed.
- Input limits are 10,000 characters (text), 100,000 (JSON) and 200,000 (CSV).
  Documents are pasted into the form; there is no file upload.
- Invalid JSON/CSV ends as `failed` rather than `dead_letter`, because retrying
  identical input cannot succeed.
- Isolation is by tenant claim in the token, not by database row-level security.
  A bug in a query could cross tenants; the tests cover the current routes, not a
  formal guarantee.
- Alembic migrations are PostgreSQL-only by design. SQLite (development and the
  fast test run) creates its schema from the ORM models instead.

- Access control is header-based (`X-Role`), not authenticated users — see the
  TODO in `src/taskmesh/api/auth.py`.
- When `DATABASE_URL` points at PostgreSQL the API currently falls back to a
  local SQLite file, so the one-day demo runs on SQLite. Redis is optional.
- Three job types have handlers: `text.process`, `json.validate` and
  `csv.analyze`. Any other job type fails honestly through the
  retry/dead-letter path instead of pretending to succeed.
- Input limits are 10,000 characters (text), 100,000 (JSON) and 200,000 (CSV).
  Documents are pasted into the form; there is no file upload.
- Invalid JSON/CSV ends as `failed` rather than `dead_letter`, because retrying
  identical input cannot succeed.

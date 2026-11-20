# Deploying TaskMesh on Vercel with managed PostgreSQL

This guide describes a **working deployment architecture** for this repository:

| Component | Platform | What runs there |
| --- | --- | --- |
| Frontend | Vercel (static project) | React + Vite console, SPA routing |
| API | Vercel (Python project) | FastAPI as one Vercel Function |
| Database | Neon, Supabase or any PostgreSQL 13+ | Jobs, workers, events, Alembic version |
| Worker | Render Background Worker | `python -m taskmesh.worker` |
| Scheduler | Render Background Worker | `python -m taskmesh.scheduler` |
| Redis (recommended) | Upstash or any `redis://` / `rediss://` provider | Scheduler lock, live event fan-out, shared job-submission limiter |

```
 Browser
   │  HTTPS
   ▼
 Vercel: frontend (taskmesh.vercel.app)
   │  HTTPS + CORS + Bearer JWT
   ▼
 Vercel: API (taskmesh-api.vercel.app)  ──────►  Managed PostgreSQL
                                                   ▲
 Render: worker  ──────────────────────────────────┤
 Render: scheduler ────────────────────────────────┘
   │
   └──► Redis (lock, fan-out, shared limiter)
```

The API only **creates and reads** jobs. Execution happens in the worker, exactly
as it does with Docker Compose. Nothing about the job model changes on Vercel.

> This guide is written from the repository's actual code and was validated
> locally (FastAPI entrypoint, PostgreSQL, worker, scheduler, all three
> workloads). No Vercel, Neon, Render or Upstash account is configured here, so
> the platform-side steps below have not been executed as part of this change.

## 1. Why two Vercel projects

A single Vercel project can serve a static frontend and an ASGI function, but
that ties the frontend build to the API deployment and makes routing rules
interact. This repository therefore uses **two projects from one repository**:

- **API project** — Root Directory `/` (the repository root). Vercel detects
  `pyproject.toml`, installs the runtime dependencies, loads `api/index.py` and
  routes every request to the FastAPI app (`/health`, `/docs`, `/jobs`, …).
- **Frontend project** — Root Directory `frontend`. Vercel detects Vite, builds
  `dist/` and applies the SPA rewrite in `frontend/vercel.json`.

Communication is cross-origin, so the API's `CORS_ORIGINS` must contain the
frontend's exact origin. There is no shared proxy in production.

Alternative: one project with a `/api` rewrite. It works, but every frontend
deploy then redeploys the Python function and CORS/SPA rules compete; the split
is easier to operate and roll back.

## 2. What the repository already provides

| File | Purpose |
| --- | --- |
| `api/index.py` | Vercel Python entrypoint; imports the existing `taskmesh.api.main:app` |
| `vercel.json` | Function `maxDuration` (60 s) and bundle exclusions for the API project |
| `.python-version` | Pins Python 3.12 (Vercel's supported default) |
| `.vercelignore` | Keeps local caches, tests and the frontend out of the API upload |
| `frontend/vercel.json` | SPA fallback so `/jobs` etc. survive a refresh |
| `frontend/.env.example` | Documents `VITE_API_BASE_URL` |
| `render.yaml` | Render Blueprint for the worker **and** scheduler services |
| `Dockerfile`, `docker-compose.yml` | Unchanged; still the local/self-hosted path |

Deployment-specific behaviour added to the application:

- **Managed provider URLs are accepted as-is.** Neon/Supabase hand out
  `...?sslmode=require&channel_binding=require`. asyncpg cannot take `sslmode`
  as a keyword, so `taskmesh.config.asyncpg_connection()` keeps `DATABASE_URL`
  verbatim and passes `ssl=require` to asyncpg as a connect argument while
  dropping `channel_binding` (TLS stays enforced). Alembic keeps using the
  original `sslmode` value through psycopg2.
- **`DB_DISABLE_POOL=true`** opens one connection per request (`NullPool`).
  Serverless instances are short-lived, and a large pool on every instance
  exhausts a managed database's connection limit.
- **Vercel cannot host the background loops.** When `VERCEL` is set, the API
  refuses to start the lifespan if `EMBEDDED_WORKER` or
  `EMBEDDED_SCHEDULER` is true, instead of silently polling inside a request.
- **The worker and scheduler configure logging on their own**, so Render shows
  structured JSON logs; the scheduler now also handles `SIGTERM` correctly
  (the previous `os.SIGTERM` lookup always returned `None`).

## 3. PostgreSQL setup

1. Create a project/database with Neon, Supabase, or another PostgreSQL 13+
   provider. Create a dedicated database (for example `taskmesh`) and a user
   that owns it.
2. Copy the provider's connection string. Neon's **direct** (unpooled) host is
   recommended for this application; see §3.2 for pooled endpoints.
3. Convert it to SQLAlchemy's asyncpg scheme:

   ```
   postgresql+asyncpg://USER:PASSWORD@HOST:5432/taskmesh?sslmode=require
   ```

   Keep `sslmode=require` (and `channel_binding=require` if the provider adds
   it). The application translates them for asyncpg; Alembic converts the same
   URL to `postgresql+psycopg2` and passes them to psycopg2 unchanged.

4. URL-encode special characters in the password (`@` → `%40`, `#` → `%23`,
   `:` → `%3A`). A raw `@` in a password breaks URL parsing.

### 3.1 Apply the migrations

Migrations are **not** run by the Vercel function (and must not be: the schema
is created once, not per request or per cold start). Run them from a machine
that can reach the database, before the first API deployment and after every
schema change:

```bash
DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@HOST:5432/taskmesh?sslmode=require' \
  alembic upgrade head

DATABASE_URL='postgresql+asyncpg://USER:PASSWORD@HOST:5432/taskmesh?sslmode=require' \
  alembic check   # fails if models and migrations have drifted
```

Alembic refuses to run against SQLite by design. `AUTO_CREATE_SCHEMA` must stay
`false` in production; the configuration loader rejects `true`.

### 3.2 Pooled vs direct connection strings

Neon offers a `-pooler` host (PgBouncer) and Supabase offers Supavisor. Those
endpoints multiplex many clients onto fewer server connections. asyncpg uses
**prepared statements**, which transaction-mode poolers do not support without
`statement_cache_size=0` — TaskMesh does not expose that knob. For this
application:

- Prefer the **direct** connection string with `DB_DISABLE_POOL=true`.
- Keep the API's concurrency modest (it is a demo-scale workload).
- Watch the provider's connection limit; each concurrent Vercel invocation may
  hold one connection for the duration of its queries.

If you must use a pooled endpoint, verify a `POST /jobs/` and a `GET /jobs/{id}`
succeed before relying on it.

## 4. API on Vercel

1. Vercel Dashboard → **Add New → Project** → import `Shridipa/TaskMesh`.
2. Configure:
   - **Root Directory**: repository root (leave empty).
   - **Framework Preset**: FastAPI (auto-detected from `pyproject.toml` and
     `api/index.py`).
   - **Build Command**: leave the default. There is nothing to build; Vercel
     installs dependencies and bundles the function.
   - **Install Command**: leave the default (`pyproject.toml` is supported).
   - **Output Directory**: leave empty (serverless function, no static output).
3. Add the environment variables from §6 to **Production** and **Preview**.
   `EMBEDDED_WORKER=false` and `EMBEDDED_SCHEDULER=false` are mandatory; with
   `VERCEL` set, the app fails its lifespan with a clear error otherwise.
4. Deploy. The first request may cold-start; subsequent ones reuse the instance.
5. Verify:

   ```bash
   curl -fsS https://YOUR-API.vercel.app/health
   # {"status":"ok"}

   curl -fsS https://YOUR-API.vercel.app/ready
   # {"status":"ready","checks":{"database":true,"redis":true},...}

   curl -fsS -X POST https://YOUR-API.vercel.app/auth/token \
     -H 'Content-Type: application/json' \
     -d '{"api_key":"YOUR_ADMIN_KEY"}'
   ```

   OpenAPI UI: `https://YOUR-API.vercel.app/docs`.

If `/ready` returns 503 with `"redis": false`, the database is fine but Redis is
not configured. In production Redis is required for readiness even though job
creation and reads still work.

### Function limits that matter

- **Duration**: configured to 60 s in `vercel.json` (Hobby maximum). Requests
  are short: they create or read a row. Long jobs must never run in the API.
- **Request body**: Vercel caps request bodies (4.5 MB). TaskMesh's own cap is
  `MAX_REQUEST_BYTES` (2 MiB) and the workloads cap input at 10k/100k/200k
  characters.
- **Filesystem**: `/tmp` only, no persistence. TaskMesh stores state in
  PostgreSQL, never on disk.
- **No background loops**: enforced by the startup guard described in §2.
- **Cold starts**: the first request in a new instance pays Python import and
  connection setup; health checks may be slower than warm requests.

## 5. Frontend on Vercel

1. **Add New → Project** → import the same repository.
2. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Vite (auto-detected)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Environment variable (Production and Preview):

   ```
   VITE_API_BASE_URL=https://YOUR-API.vercel.app
   ```

   No trailing slash and no `/api` suffix: the client appends `/auth/token`,
   `/jobs/`, etc. Vite inlines `VITE_*` at build time, so changing this value
   requires a redeploy.
4. Deploy, then set the API's `CORS_ORIGINS` to this exact origin (including
   the `https://` scheme, no trailing slash) and redeploy the API if it changed.
5. Verify direct navigation and refresh on `/jobs`, `/workers`, `/analytics`
   and `/settings` — `frontend/vercel.json` rewrites unknown paths to
   `index.html`.

## 6. Environment variables

### API project (Vercel)

| Variable | Value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql+asyncpg://…/taskmesh?sslmode=require` |
| `REDIS_URL` | `rediss://default:PASSWORD@HOST:6379` (Upstash) |
| `AUTH_JWT_SECRET` | 32+ random characters (`openssl rand -hex 32`) |
| `AUTH_API_KEYS` | `admin-key:admin:default,viewer-key:viewer:default` |
| `WORKER_SECRET` | 32+ random characters, identical on Render |
| `CORS_ORIGINS` | `https://YOUR-FRONTEND.vercel.app` |
| `AUTO_CREATE_SCHEMA` | `false` |
| `EMBEDDED_WORKER` | `false` (mandatory) |
| `EMBEDDED_SCHEDULER` | `false` (mandatory) |
| `DB_DISABLE_POOL` | `true` |
| `LOG_FORMAT` | `json` |
| `METRICS_PUBLIC` | `false` unless a scraper needs the endpoint |

Optional: `AUTH_TOKEN_TTL_SECONDS`, `RATE_LIMIT_SUBMISSIONS`,
`RATE_LIMIT_WINDOW_SECONDS`, `MAX_REQUEST_BYTES`, `AUTH_JWT_ISSUER`,
`AUTH_JWT_AUDIENCE`, `LOG_LEVEL`.

### Frontend project (Vercel)

| Variable | Value |
| --- | --- |
| `VITE_API_BASE_URL` | `https://YOUR-API.vercel.app` |

Never put API keys, JWT secrets or the worker secret in a `VITE_*` variable:
Vite inlines them into the public JavaScript bundle.

### Worker and scheduler (Render)

`render.yaml` sets `PYTHON_VERSION`, `ENVIRONMENT=production`,
`AUTO_CREATE_SCHEMA=false`, `EMBEDDED_WORKER=false`,
`EMBEDDED_SCHEDULER=false`, `LOG_FORMAT=json` and `DB_DISABLE_POOL=false`.
Enter these marked `sync: false` in the dashboard, using **the same values as
the API**:

`DATABASE_URL`, `REDIS_URL`, `WORKER_SECRET`, `AUTH_JWT_SECRET`,
`AUTH_API_KEYS`, `CORS_ORIGINS`.

The worker does not issue tokens, but TaskMesh validates the complete
production configuration in every process, so the auth variables must be
present and consistent.

## 7. Worker and scheduler on Render

Why not Vercel? A worker needs a process that keeps polling. A Vercel Function
is request-scoped: it is frozen between requests and scaled per request, so a
poll loop there would be unreliable and could execute a job twice.

1. Render Dashboard → **New → Blueprint** → select this repository. Render
   reads `render.yaml` and proposes two **Worker** services.
2. Apply the Blueprint, then fill in the `sync: false` variables for both
   services (same values as the API).
3. Deploy. Render runs:

   ```
   pip install --no-cache-dir .
   python -m taskmesh.worker     # service taskmesh-worker
   python -m taskmesh.scheduler  # service taskmesh-scheduler
   ```

   Run **both**. The worker leases and executes jobs; the scheduler releases
   `execute_at` jobs, requeues jobs whose worker lease expired, and marks
   stale workers inactive. Without the scheduler, retries and scheduled jobs
   stay in `scheduled` forever.
4. Logs are JSON on stdout (`LOG_FORMAT=json`). Look for `Worker starting`,
   `Job completed`, `Job failed`, `Scheduler starting`. Render restarts a
   worker whose process exits; TaskMesh drains the current job on `SIGTERM`.
5. Scale the worker service horizontally for more throughput. Each worker is
   safe: PostgreSQL `FOR UPDATE SKIP LOCKED` prevents double leasing, and
   completions are rejected from a worker that lost its lease.

Redis is optional for the scheduler (it falls back to polling without the
distributed lock) but required by the API's production readiness check.

## 8. Authentication and secrets

- Users exchange an API key at `POST /auth/token`; the key format is
  `key:role:tenant`, roles are `admin`, `developer`, `viewer`. Keys must be at
  least 8 characters and are compared in constant time.
- The API returns an HS256 JWT (`sub`, `role`, `tenant`, `iss`, `aud`, `exp`).
  Every protected request verifies signature, issuer, audience and expiry.
- Workers authenticate with the shared `X-Worker-Token` header
  (`WORKER_SECRET`), not with a user JWT.
- Generate secrets with:

  ```bash
  openssl rand -hex 32   # AUTH_JWT_SECRET and WORKER_SECRET
  openssl rand -base64 24 | tr -d '/+='   # an API key
  ```

- Use different values for local development, preview and production. Never
  commit them. Vercel encrypts environment variables; Render stores them as
  service secrets. Repository `.env` files stay untracked.
- Tokens are stateless: rotating `AUTH_JWT_SECRET` invalidates every issued
  token immediately. Rotating an API key only stops new exchanges.

## 9. CORS

- `CORS_ORIGINS` is a comma-separated allowlist of exact origins. Production
  refuses an empty list or `*`.
- Set it to the frontend origin, for example
  `https://taskmesh.vercel.app`. Preview deployments have a different origin
  per deployment; either add each preview origin temporarily or keep the
  default production domain and point previews at the production API.
- `allow_credentials` is off, so no cookies are used; the bearer token is sent
  in the `Authorization` header, which is in the allowed header list.
- Trailing slashes matter: `https://app.example.com/` does not match
  `https://app.example.com`.

## 10. Verifying a deployment

```bash
API=https://YOUR-API.vercel.app
KEY=YOUR_ADMIN_KEY

# 1. Health and readiness
curl -fsS "$API/health"
curl -fsS "$API/ready"

# 2. Authentication
TOKEN=$(curl -fsS -X POST "$API/auth/token" \
  -H 'Content-Type: application/json' \
  -d "{\"api_key\":\"$KEY\"}" | python -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')

# 3. Text workload
JOB=$(curl -fsS -X POST "$API/text/jobs" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Deployed check. Two sentences!"}' | python -c 'import json,sys;print(json.load(sys.stdin)["id"])')
sleep 3 && curl -fsS "$API/text/jobs/$JOB"

# 4. JSON workload
curl -fsS -X POST "$API/analysis/jobs" -H 'Content-Type: application/json' \
  -d '{"task":"json.validate","content":"{\"a\":[1,2]}"}'

# 5. CSV workload
curl -fsS -X POST "$API/analysis/jobs" -H 'Content-Type: application/json' \
  -d '{"task":"csv.analyze","content":"name,score\nAda,90\nGrace,80\n"}'

# 6. Authenticated management endpoints
curl -fsS "$API/jobs/" -H "Authorization: Bearer $TOKEN"
```

A job that stays `pending` means no worker is leasing jobs: check the Render
worker logs and that both services use the same `DATABASE_URL`.

The repository also ships an end-to-end smoke script:

```bash
cd frontend
API_BASE="$API" ADMIN_API_KEY="$KEY" python ../scripts/live_smoke.py
```

It checks authentication, tenant scoping, all three workloads, deterministic
failures, rate limiting and CORS against a running deployment.

## 11. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Vercel build fails on dependencies | Python version/deps mismatch | Keep `.python-version` at 3.12; do not add unsupported packages |
| Function returns 500, logs `EMBEDDED_WORKER and EMBEDDED_SCHEDULER must both be false` | Background loops enabled on Vercel | Set both to `false`, redeploy, run the worker on Render |
| Function returns 500, logs `DATABASE_URL must use a supported async driver` | URL still starts with `postgresql://` | Use `postgresql+asyncpg://` |
| `connect() got an unexpected keyword argument` at startup | Custom URL params other than `sslmode`/`channel_binding` | Remove provider-only params; keep `sslmode` |
| `/ready` → 503, `redis:false` | No Redis / wrong URL in production | Set `REDIS_URL` (Upstash uses `rediss://`), redeploy |
| `/ready` → 503, `database:false` | Wrong password, host, or `sslmode`; database asleep | Test the URL with `psql`, check provider status |
| Browser error `blocked by CORS policy` | `CORS_ORIGINS` lacks the exact frontend origin | Add the origin (scheme + host, no slash), redeploy API |
| Frontend loads, all API calls 404 | `VITE_API_BASE_URL` missing or includes `/api` | Set it to the API origin, rebuild the frontend |
| Refresh on `/jobs` returns 404 | Missing SPA rewrite | Keep `frontend/vercel.json`; Root Directory must be `frontend` |
| Jobs stay `pending` | Worker not running or different database | Start `taskmesh-worker`, compare `DATABASE_URL` |
| Jobs stay `scheduled` after a retry | Scheduler not running | Start `taskmesh-scheduler` |
| `prepared statement ... already exists` | asyncpg against a transaction pooler | Use the direct connection string, or a session-mode pooler |
| `too many connections` | Pool too large or too many warm instances | Keep `DB_DISABLE_POOL=true`, lower concurrency, upgrade the plan |
| `POST /auth/token` → 401 | Key not in `AUTH_API_KEYS`, or wrong environment | Compare the exact key and role list, redeploy |
| `POST /auth/token` → 429 | 10 token requests/minute per instance | Wait a minute; this limiter is per instance |
| `GET /jobs/` → 401 | Missing/expired bearer token | Re-run the token exchange |
| Render service exits immediately | Missing auth variables (production validation) | Set all variables from §6, restart |

Deployment logs:

- Vercel: Project → Deployments → Functions → Logs. Every response carries an
  `X-Request-ID`; the same id is in the JSON log line.
- Render: service → Logs (JSON lines with `job_id`, `worker_id`, `status`).

## 12. Limitations of this architecture

- **Rate limiting is per instance.** The public demo limiter and the token
  limiter are in-process (`SlidingWindowLimiter`); with several warm Vercel
  instances each enforces its own budget. The engine's per-tenant submission
  limiter uses Redis and is shared. For strict global limits, put a WAF/edge
  rate limit in front of the API.
- **60-second function limit.** Fine for creating and reading rows; never move
  job execution into the API.
- **No automatic migrations.** Run `alembic upgrade head` yourself; the API
  cannot create the schema in production.
- **Redis is a hard readiness dependency in production.** Without it `/ready`
  stays 503 even though most endpoints work.
- **No server-side session store.** JWTs cannot be revoked individually; rotate
  the signing secret to invalidate all of them.
- **Cold starts** add latency to the first request per instance.
- **Tenant isolation** comes from the token's `tenant` claim and route-level
  scoping, not database row-level security.
- **At-least-once execution.** A handler with external side effects can run
  twice if a lease expires; TaskMesh rejects late completions but cannot undo
  side effects.
- **No per-job timeout.** A pathological input can occupy a worker.
- **Preview deployments** have per-deployment origins; they need their own
  `CORS_ORIGINS` entry or must use the production API.
- **Local verification was not a platform deployment.** The Vercel and Render
  configurations were validated as files and the application path was exercised
  locally; the first real deploy still needs the platform steps above.

## 13. Deployment checklist

**Repository**

- [ ] Working on `main`, tests and build passing
- [ ] `alembic upgrade head` and `alembic check` clean against the production DB

**PostgreSQL**

- [ ] Database and user created
- [ ] `DATABASE_URL` uses `postgresql+asyncpg://` and `sslmode=require`
- [ ] Migrations applied
- [ ] Password URL-encoded

**Vercel API**

- [ ] Root Directory `/`, FastAPI detected, `api/index.py` entrypoint
- [ ] All variables from §6 set for Production and Preview
- [ ] `EMBEDDED_WORKER=false`, `EMBEDDED_SCHEDULER=false`, `DB_DISABLE_POOL=true`
- [ ] `/health` is 200, `/ready` is 200, `/docs` loads
- [ ] Token exchange works; `/jobs/` requires a token

**Vercel frontend**

- [ ] Root Directory `frontend`, Vite detected, output `dist`
- [ ] `VITE_API_BASE_URL` points at the API origin
- [ ] `CORS_ORIGINS` contains this origin
- [ ] Direct navigation/refresh works on all routes

**Render worker + scheduler**

- [ ] Both services created from `render.yaml`
- [ ] Same database, Redis, `WORKER_SECRET` and auth variables as the API
- [ ] Logs show `Worker starting` and `Scheduler starting`
- [ ] Text, JSON and CSV jobs complete with a `worker_id`

**Security**

- [ ] Fresh 32+ character JWT and worker secrets
- [ ] API keys are not development defaults
- [ ] No secret in Git, `VITE_*` variables, or logs
- [ ] CORS is an explicit origin list, not `*`

**Final**

- [ ] `scripts/live_smoke.py` passes against the deployed API
- [ ] Jobs persist after an API/worker restart
- [ ] Rate limiting and error responses behave as documented

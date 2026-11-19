# TaskMesh application image — used by the API, worker and scheduler services.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime tools: netcat for dependency waiting, curl for health probes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends netcat-openbsd curl \
    && rm -rf /var/lib/apt/lists/*

# Dependency layer: copy the manifest and a stub package so pip can resolve the
# project without invalidating the cache on every source change.
COPY pyproject.toml ./
RUN mkdir -p src/taskmesh && touch src/taskmesh/__init__.py \
    && pip install --no-cache-dir .

# Application source (only this layer changes during development).
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY wait-for-deps.sh ./
RUN pip install --no-cache-dir --no-deps . \
    && chmod +x /app/wait-for-deps.sh

# Run as an unprivileged user.
RUN useradd --create-home --shell /bin/false --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Exec form keeps PID 1 signal handling correct so SIGTERM triggers a graceful
# shutdown of the API, worker or scheduler.
ENTRYPOINT ["/app/wait-for-deps.sh"]
CMD ["sh", "-c", "alembic upgrade head && uvicorn taskmesh.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]

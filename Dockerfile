FROM python:3.12-slim

WORKDIR /app

# Install system dependencies first (separate layer for caching)
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Copy only the package manifest first to cache the dependency layer
COPY pyproject.toml ./

# Create a minimal src layout so pip can resolve the package
RUN mkdir -p src/taskmesh && touch src/taskmesh/__init__.py
RUN pip install --no-cache-dir -e .

# Now copy the full source (invalidates cache only when source changes)
COPY . .

# Re-install in case source changed (no-cache is fast when deps are cached)
RUN pip install --no-cache-dir -e .

# Create non-root user and fix permissions
RUN useradd --no-create-home --shell /bin/false appuser && \
    chown -R appuser:appuser /app

# Make wait script executable
RUN chmod +x /app/wait-for-deps.sh

USER appuser

EXPOSE 8000

# Use exec form with entrypoint for proper PID-1 / signal handling
ENTRYPOINT ["/app/wait-for-deps.sh"]
CMD ["sh", "-c", "alembic upgrade head && uvicorn taskmesh.main:app --host 0.0.0.0 --port 8000"]

---
name: architectural_refactor
description: Comprehensive guide for performing a full architectural cleanup of the TaskMesh project, consolidating SQLAlchemy Base, separating ORM and Pydantic models, fixing imports, and ensuring test compatibility.
source: auto-skill
extracted_at: '2026-06-28T06:32:33.165Z'
---

# Architectural Refactor Procedure

This skill captures the step‑by‑step approach used to transform the TaskMesh codebase into a clean, production‑ready layered architecture.

## 1. Consolidate SQLAlchemy Base
- Create a single `Base` class in `taskmesh/db/base.py` extending `DeclarativeBase`.
- Remove all other `Base` definitions (e.g., in `taskmesh/__init__.py` and `taskmesh/db/__init__.py`).
- Re‑export the new `Base` from those modules with `from .db.base import Base`.
- Update all ORM model files to import `Base` from `.db.base`.

## 2. Separate ORM and Pydantic Schemas
- Keep only SQLAlchemy model definitions in `taskmesh/db/models.py`.
- Keep all request/response schemas in `taskmesh/models.py` (Pydantic only).
- Ensure no ORM classes are imported into the Pydantic module and vice‑versa.

## 3. Fix Package Imports & Circular Dependencies
- Use absolute imports for top‑level package references (`from taskmesh.db import Base`).
- In API modules, import models via `from ..db import models` to trigger registration without creating cycles.
- Verify `taskmesh.main` imports cleanly after changes.

## 4. Database Initialization
- In `api/dependencies.py`, import `Base` (which also registers models) and call `Base.metadata.create_all` inside an async context (`create_schema`).
- Ensure the tables `jobs`, `workers`, and `events` are present.
- Remove any legacy initialization code or duplicate files (`db_legacy.py`).

## 5. Reorganize Project Layout
- Follow the target structure:
```
taskmesh/
    api/
        routes/
        services/
        auth.py
        dependencies.py
        main.py
    db/
        __init__.py
        base.py
        models.py
    models.py          # Pydantic only
    engine.py
    scheduler.py
    worker.py
```
- Delete obsolete directories (e.g., old `backend/`).

## 6. Business Logic Refactor
- Keep the `TaskMeshEngine` as the primary service implementation.
- Expose a thin wrapper in `api/services/job_service.py` that re‑exports the engine singleton.
- Route handlers call the service methods; they perform no direct DB logic.

## 7. ID Handling Compatibility
- Store primary keys as string UUIDs (`str(uuid.uuid4())`).
- Remove UUID objects from INSERT statements to avoid SQLite binding errors.
- Adjust helper methods (`get_job`, `lease_job_by_id`, etc.) to use string IDs directly.

## 8. Preserve API Compatibility
- Do not change endpoint URLs or response schemas.
- Maintain backward‑compatible helpers (`_orm_to_dict`) that convert ORM instances to Pydantic models.

## 9. Update Imports
- Remove any stale imports of old modules or duplicate `Base` symbols.
- Ensure only necessary symbols are imported in each file.

## 10. Verification
- Run the full test suite (`pytest`). All tests should pass.
- Confirm that `Base.metadata.tables` lists the expected tables.
- Check that Alembic migrations reference the single `Base`.

## 11. Code Quality
- Apply PEP‑8 formatting, add type hints where missing, and delete dead/commented code.
- Ensure the code runs on Python 3.10+.

---

**Why this works:**
- A single `Base` eliminates circular imports and ensures Alembic sees one metadata source.
- Clear separation of ORM vs. Pydantic models reduces coupling and simplifies testing.
- Consistent import style prevents hidden dependencies and import errors.
- Storing IDs as strings makes the SQLite test database portable while keeping production PostgreSQL compatibility.

This procedure can be reused for future large‑scale refactors in similar Python FastAPI projects.

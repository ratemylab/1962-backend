# Alembic migrations (SQLAlchemy)

Use **Alembic** for versioned schema migrations alongside SQLAlchemy models. When you add or change database-backed API surface (tables, columns, indexes, constraints), create or update **Alembic revision files** so the database schema matches your models.

Projects using raw SQL migration tools (e.g. Flyway with hand-written SQL in `db/`) are valid but outside this skill’s default workflow.

## Typical layout

```
project/
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
│       ├── <revision>_create_users_table.py
│       └── ...
├── app/
│   └── db/
│       └── models/
└── ...
```

- **Config:** `alembic.ini` at the project root (or path passed with `-c`).
- **Revisions:** Python modules under `migrations/versions/` (name often `<revision>_<slug>.py`).
- **Order:** Revisions form a chain via `revision` / `down_revision`; never edit applied migrations in production—add a new revision instead.

## Workflow

1. Change SQLAlchemy models (tables, columns, relationships).
2. Generate a revision (often autogenerate against a live DB that reflects the previous state):

   ```bash
   alembic revision --autogenerate -m "describe_change"
   ```

3. **Review** the generated `upgrade()` / `downgrade()`—autogenerate can miss renames, drops, or server defaults.
4. Apply:

   ```bash
   alembic upgrade head
   ```

5. Commit the new file under `migrations/versions/` with your code changes.

## Async engines

If the app uses `asyncpg` and an async SQLAlchemy engine, `env.py` is often configured to run migrations with a **sync** URL (e.g. `postgresql://` with `psycopg2`) or uses `run_sync` patterns—follow your template’s `migrations/env.py` and `alembic.ini` as the source of truth.

## Naming and hygiene

- Use clear revision messages: `add_user_email_index`, `create_posts_table`.
- One logical change per revision when possible; large refactors may split across several revisions.
- Keep models and migrations aligned: the validator expects revision files under `migrations/versions/` when SQLAlchemy `Column` models are present.

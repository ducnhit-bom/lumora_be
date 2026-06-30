# Lumora Backend

FastAPI backend for Lumora.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

Create a local `.env` file if your shell or process manager loads env files. Do not commit secrets.
Use `.env.example` as the template.

| Key | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Lumora API` | FastAPI title. |
| `APP_ENV` | `development` | Runtime environment label. |
| `LOG_LEVEL` | `INFO` | Python logging level for request and validation logs. |
| `DATABASE_URL` | `postgresql+psycopg://lumora:lumora@localhost:5432/lumora` | PostgreSQL connection string. Use the Supabase URL in local `.env`. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins for local/web development. |

### Supabase Database

Lumora currently uses PostgreSQL via SQLAlchemy and `psycopg`, so Supabase works without changing the database driver.

1. Open Supabase Dashboard -> Project Settings -> Database -> Connection string.
2. Copy either the direct connection string or session pooler string.
3. Convert the scheme for SQLAlchemy/psycopg:

```text
postgresql://...
```

to:

```text
postgresql+psycopg://...
```

4. Save it in local `.env` as `DATABASE_URL`.

If the database password contains special characters, URL-encode them before saving the URL.

| Character | Encoded |
| --- | --- |
| `@` | `%40` |
| `#` | `%23` |
| `/` | `%2F` |
| `?` | `%3F` |
| `%` | `%25` |

Example direct connection:

```bash
DATABASE_URL="postgresql+psycopg://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres"
```

Example session pooler connection:

```bash
DATABASE_URL="postgresql+psycopg://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres"
```

For local development, direct connection is fine. For hosted runtimes, prefer Supabase pooler when connection limits matter.

## Run

```bash
uvicorn app.main:app --reload
```

API health check: `http://127.0.0.1:8000/health`

API docs: `http://127.0.0.1:8000/docs`

## Migrations

```bash
alembic revision --autogenerate -m "message"
alembic upgrade head
```

## Checks

```bash
python3 -m py_compile app/main.py
python3 -m unittest tests.test_foundation
python3 -m unittest discover -s tests
```

## Railway Staging

The repo includes `Dockerfile` and `railway.json` for Railway staging. Configure these variables in Railway before deploying:

- `APP_ENV=staging`
- `DATABASE_URL` using the Supabase PostgreSQL URL with `postgresql+psycopg://`
- `CORS_ORIGINS` for any hosted frontend origin that will call the API
- `LOG_LEVEL=INFO`

The container runs `alembic upgrade head` before starting Uvicorn.

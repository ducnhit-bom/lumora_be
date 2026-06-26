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

| Key | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Lumora API` | FastAPI title. |
| `APP_ENV` | `development` | Runtime environment label. |
| `DATABASE_URL` | `postgresql+psycopg://lumora:lumora@localhost:5432/lumora` | PostgreSQL connection string. |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins for local/web development. |

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
```

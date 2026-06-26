# AGENTS.md

This file provides guidance to OpenCode when working in the Lumora FastAPI backend repo.

## Repo Role

**Name:** lumora_be
**Stack:** Python, FastAPI, Uvicorn
**Purpose:** Lumora API service.

## Read First

- `./README.md`
- `./requirements.txt`
- API and architecture context in `./lumora_brain/documents/` when changing contracts or behavior.

## Cross-Repo Link

- `./lumora_brain` is a symlink to `../lumora_brain`.
- Use it for product/spec/API context. Prefer editing brain docs via `../lumora_brain` when possible.

## FastAPI Rules

- Keep route handlers small; move reusable business logic into dedicated modules when repetition appears.
- Use typed request/response models when adding real endpoints.
- Keep API responses stable once consumed by the Flutter app.
- Do not introduce database, auth, background jobs, or infrastructure layers until the feature requires them.
- Prefer explicit errors and status codes over generic exceptions.

## Python Rules

- Use standard library features before adding dependencies.
- Keep imports sorted by standard library, third-party, local modules.
- Avoid hidden global state unless it is FastAPI app configuration or a deliberate singleton.
- Add tests before or alongside non-trivial business logic once a test framework is introduced.

## Verification

- Run `python3 -m py_compile app/main.py` after small syntax-level changes.
- Run the local API with `uvicorn app.main:app --reload` for endpoint/runtime checks.
- If dependencies changed, verify in a virtual environment using `pip install -r requirements.txt`.

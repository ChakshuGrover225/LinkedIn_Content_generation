# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A web app, deployed on AWS EC2, that takes a topic, has an LLM write a LinkedIn post draft, critique it, and revise it, then shows the postable result. Stack: React (Vite) frontend → FastAPI backend → three sequential LLM agents served by a local Ollama server through the **Anthropic SDK** (Ollama exposes an Anthropic-compatible `/v1/messages` endpoint). The default model is `gpt-oss:20b-cloud`, an Ollama cloud model, so Ollama must be running and signed in (`ollama signin`).

Development happens on Windows (PowerShell); production is Ubuntu 24.04 (Python 3.12), so avoid Python 3.13-only features. The frontend needs Node ≥ 22.22 (required by react-router 8).

## Commands

```powershell
pip install -r requirement.txt                     # note: singular filename

# Backend (must be started from inside backend/, so `app` and `logic` are importable)
cd backend; python -m uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs   health: GET /api/health

# Run the agent chain without the API
python backend/orchestrator.py                                   # prints the revised post
cd backend; python -m logic.generate_linkedin_post "some topic"  # prints draft, critique, revised

# Frontend (dev server on :5173, proxies /api to :8000)
cd frontend; npm install; npm run dev
npm run build      # outputs frontend/dist
```

There is no test suite, linter or formatter configured.

## Architecture

**Request flow:** `frontend/src/pages/HomePage.jsx` → `api.js` POSTs `{topic}` to `/api/generate` → `backend/app/routes.py` → `logic.generate_linkedin_post.generate_linkedin_post(topic)` (the orchestrator) builds an `anthropic.Anthropic` client and three `Agent`s, then runs writer → critic → reviser sequentially and returns `{draft, critique, revised}`. The route adds `topic`. The frontend saves the result to router state and `sessionStorage` (`lastResult.js`) and renders it on `/output`.

**Python package layout:** `backend/` is the import root; `app` (FastAPI: `main.py`, `routes.py`, `schemas.py`) and `logic` (LLM code) are packages. `logic/generate_linkedin_post.py` uses a relative import (`from . import settings`), so it fails with "attempted relative import" if run directly as a file. Run it via `python -m` from `backend/`, or via `backend/orchestrator.py`. `logic/build_linkedin_post.py` is the original development scratch script: it uses a bare `import settings`, prints at import time, and only runs from inside `backend/logic/`. The API does not use it; don't import it.

**Configuration:** everything lives in `backend/logic/settings.py`, as pydantic models instantiated at import time (`settings.settings`). Environment overrides are read **once at import** from the repo-root `.env` (`load_dotenv` does not override variables already set): `LLM_MODEL`, `LLM_BASE_URL` (default `http://localhost:11434`), `OLLAMA_API_KEY` (a local Ollama ignores it), `CORS_ORIGINS`. Changing `.env` needs a backend restart, because `--reload` only watches `.py` files.

**Prompts:** `backend/logic/prompts/{writer,critic,reviser}_v1.md`, with paths anchored to `settings.py`'s directory so they resolve on both Windows and Linux. They are re-read on every request. An empty or missing file falls back to the `DEFAULT_*_PROMPT` constants in `generate_linkedin_post.py`. Only the writer prompt limits length, so the reviser tends to produce long markdown posts (tables, headings) with invented statistics. Prompt quality is the main lever on output.

**Error handling:** `routes.py` maps Anthropic SDK exceptions to HTTP errors with a user-facing `detail`: timeout → 504, connection failure (Ollama down) → 503, model not found → 502, auth → 502, rate limit → 429, other `APIError`/`EmptyResponseError` → 502. The `except` order matters: `APITimeoutError` subclasses `APIConnectionError`. `frontend/src/api.js` shows `detail` (a string, or the first `msg` of FastAPI's 422 validation list). The generate route is deliberately a sync `def`, so the blocking LLM calls run in FastAPI's threadpool.

**Cross-boundary contracts to keep in sync:**
- `MAX_TOPIC_LENGTH = 2000` is duplicated in `backend/app/schemas.py` and `frontend/src/pages/HomePage.jsx`.
- The response shape `{topic, draft, critique, revised}` (`GenerateResponse`) is consumed directly by `OutputPage.jsx`.

**Frontend specifics:**
- **Routing:** react-router v8 in declarative mode; import from `"react-router"`, not `react-router-dom`.
- **Markdown:** rendered with react-markdown v10 + `remark-gfm` (the model emits tables and task lists) + `remark-breaks` (keeps the single line breaks LinkedIn posts rely on). Raw HTML is intentionally not enabled (no `rehype-raw`), so LLM output can't inject markup.
- **Copy button:** copies the rendered `innerText`, not the markdown source, because LinkedIn doesn't render markdown.
- **Styling:** plain CSS with light/dark color tokens in `src/index.css`; no CSS framework.
- **API address:** `VITE_API_BASE_URL` (set at build time) defaults to empty, so requests go to `/api` on the same origin. In dev the Vite proxy (`vite.config.js`) forwards them; in production nginx does.

## Docs that mirror the code

`user_manual.md` (local setup and run) and `deployment_guide.md` (EC2: nginx, systemd unit `linkedin-backend`, web root `/var/www/linkedin-post-generator`, `deploy.sh`) contain exact commands, ports, paths, env var names and defaults. Update them when changing any of those. In production nginx needs `proxy_read_timeout 300s` on `/api/generate`, because one generation takes 15–60 s (three sequential LLM calls).

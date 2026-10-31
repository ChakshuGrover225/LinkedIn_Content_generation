# User Manual: LinkedIn Post Generator

Type a topic in the browser and get back a LinkedIn post that has been drafted, critiqued and revised by three AI agents.

```
Browser (React, :5173)  ──►  FastAPI backend (:8000)  ──►  Ollama (:11434)
                                    writer → critic → reviser
```

All commands below are for **PowerShell on Windows** and start from the project root
(the folder that contains this file), unless a step says otherwise.

---

## 1. Prerequisites

| Tool | Tested version | Check with |
|------|----------------|------------|
| Python | 3.13 | `python --version` |
| Node.js | 24.18 (needs 22.22 or newer) | `node -v` |
| Ollama | 0.32.14 | `ollama --version` |

Install Ollama from the official Ollama website if you don't have it yet. Older Ollama versions
may lack the Anthropic-compatible API this project uses, so update it if requests fail.

---

## 2. One-time setup

### 2.1 Set up Ollama and the model

```powershell
ollama signin                   # required for cloud models such as gpt-oss:20b-cloud
ollama pull gpt-oss:20b-cloud   # the model the backend uses by default
ollama list                     # gpt-oss:20b-cloud should appear in this list
```

Ollama serves its API on `http://localhost:11434` while the Ollama app is running.
If it isn't running, start the app or run `ollama serve` in a separate terminal.

### 2.2 Create the Python environment and install backend packages

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirement.txt
```

> Already have a virtual environment for this project (for example `..\DEV_ENV`)?
> Activate that one instead and run only the `pip install` line.

### 2.3 Install frontend packages

```powershell
cd frontend
npm install
cd ..
```

### 2.4 Configuration (optional)

Everything works with the defaults. To change them, add any of these lines to the `.env` file in
the project root, then restart the backend:

| Variable | Default | What it does |
|----------|---------|--------------|
| `LLM_MODEL` | `gpt-oss:20b-cloud` | Ollama model used by all three agents |
| `LLM_BASE_URL` | `http://localhost:11434` | Address of the Ollama server |
| `OLLAMA_API_KEY` | `ollama` | Ignored by a local Ollama; only needed when calling ollama.com directly |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of frontend addresses allowed to call the API |

`max_tokens`, `timeout` and `max_retries` are set in `backend/logic/settings.py`.

---

## 3. Running the project

You need **Ollama running**, plus **two terminals**: one for the backend, one for the frontend.

### Terminal 1: backend (FastAPI)

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Wait for `Uvicorn running on http://127.0.0.1:8000`. To confirm it works:

- http://localhost:8000/api/health should show `{"status":"ok"}`
- http://localhost:8000/docs is the interactive API documentation, where you can try `/api/generate`

> `uvicorn` must be started from inside the `backend` folder, otherwise it can't find `app` and `logic`.

### Terminal 2: frontend (React + Vite)

```powershell
cd frontend
npm run dev
```

Open **http://localhost:5173/home** in your browser.

### Using the app

1. On `/home`, type a topic (up to 2000 characters).
2. Click **Generate post** (or press **Ctrl+Enter**).
3. Wait while the three agents run. This usually takes 15 to 60 seconds.
4. You land on `/output`, which shows:
   - the **final post**, formatted from markdown
   - **Copy post**, which copies the post as plain text, ready to paste into LinkedIn
   - **First draft** and **Critic's feedback** in collapsible sections
   - **New post**, which takes you back to `/home`

The last result stays on `/output` if you refresh the page.

### Stopping

Press **Ctrl+C** in each terminal.

---

## 4. Testing the backend without the frontend

**Run the orchestrator script.** It prints the final post. Edit the topic inside
`backend/orchestrator.py` to try others.

```powershell
python backend\orchestrator.py
```

**Run the chain as a module.** It prints the draft, critique and revised post, and logs each agent as it runs.

```powershell
cd backend
python -m logic.generate_linkedin_post "Why side projects teach more than tutorials"
```

**Call the running API** (backend from Terminal 1 must be running):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/generate -ContentType "application/json" -Body '{"topic": "Why side projects teach more than tutorials"}'
```

---

## 5. Customizing the output

| What | Where | Needs a restart? |
|------|-------|------------------|
| Agent instructions (tone, length, format) | `backend/logic/prompts/writer_v1.md`, `critic_v1.md`, `reviser_v1.md` | No, they're read on every request |
| Model or Ollama address | `.env` (see section 2.4) | Yes, restart the backend |
| Token limit, timeout, retries | `backend/logic/settings.py` | No, `--reload` restarts the backend when you save |

If a prompt file is empty, the agent falls back to a built-in default prompt.

Tip: only the writer prompt limits length by default, so the reviser may produce long posts.
Repeat any limits (word count, plain text, no invented statistics) in `reviser_v1.md`.

---

## 6. Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Frontend shows *"Could not reach the backend. Is the FastAPI server running?"* | Backend isn't running on port 8000 | Start Terminal 1 (section 3) |
| *"Could not reach the Ollama server. Is it running?"* | Ollama isn't running | Open the Ollama app or run `ollama serve` |
| *"Model 'gpt-oss:20b-cloud' was not found on the Ollama server."* | Model not pulled | `ollama signin`, then `ollama pull gpt-oss:20b-cloud` |
| `ImportError: attempted relative import with no known parent package` | A file inside `backend/logic/` was run directly | Use `python backend\orchestrator.py` or the module command in section 4 |
| `ModuleNotFoundError: No module named 'app'` (or `'logic'`) | `uvicorn` was started outside the `backend` folder | `cd backend` first |
| `ModuleNotFoundError: No module named 'fastapi'` (or another package) | Virtual environment not active, or packages not installed | Activate `.venv`, then `pip install -r requirement.txt` |
| `Activate.ps1 cannot be loaded because running scripts is disabled on this system` | PowerShell's execution policy blocks scripts | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activation and use `.\.venv\Scripts\python.exe` in place of `python` |
| `npm.ps1 cannot be loaded ...` | Same execution policy | Use `npm.cmd run dev` instead of `npm run dev` |
| Port 8000 already in use | Another backend is still running | Stop it with Ctrl+C in its terminal; if you use a different port, also update the proxy target in `frontend/vite.config.js` |
| **Copy post** shows *"Copy failed"* | The browser only allows clipboard access on `localhost` or HTTPS | Use `http://localhost:5173`, or serve the site over HTTPS |

---

## 7. Project structure

```
LinkedIn_Content_generation/
├── .env                          # optional settings (never commit; already in .gitignore)
├── requirement.txt               # Python packages for the backend
├── user_manual.md                # this file
├── backend/
│   ├── orchestrator.py           # quick script to run the chain from the terminal
│   ├── app/
│   │   ├── main.py               # FastAPI app: logging, CORS, routes
│   │   ├── routes.py             # GET /api/health, POST /api/generate
│   │   └── schemas.py            # request/response models and topic validation
│   └── logic/
│       ├── settings.py           # all configuration
│       ├── generate_linkedin_post.py  # agents + writer → critic → reviser orchestrator
│       ├── build_linkedin_post.py     # original development script
│       └── prompts/              # system prompts for the three agents
└── frontend/
    ├── package.json
    ├── vite.config.js            # dev server; forwards /api to the backend on :8000
    └── src/
        ├── App.jsx               # routes: /home and /output
        ├── api.js                # calls POST /api/generate
        ├── pages/HomePage.jsx    # topic input
        ├── pages/OutputPage.jsx  # renders the post as markdown
        └── index.css             # styles (light and dark mode)
```

---

## 8. Production build (for a server such as EC2)

For the full, step-by-step EC2 setup (nginx, systemd, HTTPS, updates), see
[deployment_guide.md](deployment_guide.md). The short version:

1. Build the frontend with `cd frontend; npm run build`. This creates static files in `frontend/dist`.
   Serve them with a web server that falls back to `index.html` for unknown paths,
   so that `/home` and `/output` work on refresh.
2. If the API is on a different address than the frontend, set `VITE_API_BASE_URL`
   (for example `http://your-server:8000`) **before** running `npm run build`, and set
   `CORS_ORIGINS` on the backend to the frontend's address.
3. Run the backend without `--reload`, listening on all interfaces:
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` (from inside `backend`).
4. Make sure Ollama runs on the server (or point `LLM_BASE_URL` at one), and run `ollama signin` there
   if you use a cloud model.

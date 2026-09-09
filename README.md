# Online Judge (OJ) System

A small but feature-complete Online Judge system, built as the second lab
assignment of the *Programming and Training (Python)* course.

## Tech Stack

- **Backend**: FastAPI (async, `async def`), served with uvicorn.
- **Frontend**: Streamlit (Step 6), talking to the backend over REST APIs.
- **Judge**: `asyncio` + `subprocess` for async evaluation with time/memory limits.
- **Storage**: Local JSON files under `data/`.

## Project Layout

```
app/            # FastAPI backend (all endpoints are async def)
  main.py       # Application entry point (routers, error envelope, lifespan)
  config.py     # Defaults (3s/128MB limits, paths, rate limit) and settings
  utils.py      # Raw JSON body parsing (400 instead of 422)
  models/       # Pydantic models (problem, submission, language, user, ai)
  routers/      # problems / submissions / languages / auth / users / logs / system / ai
  services/     # problem_ops / judge / language_ops / submission_ops /
                # user_ops / log_ops / ai_ops / auth
frontend/       # Streamlit frontend (Step 6 + Advance UI)
  app.py
data/           # Runtime data (problems tracked; submissions/users/logs/tmp ignored)
  problems/     # One JSON file per problem
tests/          # pytest tests
```

## Module Progress

- Step 1: problem CRUD (list/detail/add/edit/delete, cascade on delete)
- Step 2: async judge (TLE/MLE/RE/CE/WA/AC), language registry, dynamic languages
- Step 3: submission list/detail/rejudge, per-user+problem rate limit
- Step 4: register/login/logout, roles (user/admin/banned), initial admin
- Step 5: judge logs, log visibility, access audit
- Step 6: Streamlit frontend (users / problems / submissions / languages / logs / AI)
- Advance: AI problem generation (model config, progress, cancel, token cost)

## Quick Start

**One-click (Windows)**: double-click `start.bat` — it opens the backend, the
frontend, and your browser automatically. Close the two command windows to
stop.

Manual alternative:

```bash
# Create a virtual environment
python -m venv .venv
# Activate it (Windows)
.venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
# Run the backend (terminal 1)
uvicorn app.main:app --reload --port 8000
# Run the frontend (terminal 2)
streamlit run frontend/app.py
# Run the API test suite (optional)
pytest tests/ -v
# Seed demo problems for the acceptance demo (optional)
python scripts/seed_demo.py
```

The system auto-creates an initial admin account on startup:
username `admin`, password `admintestpassword`.

## TA Q&A rulings implemented (from the course group chat)

| # | Ruling | Where |
|---|---|---|
| 1 | audit action is `view_logs` | `services/log_ops.py` |
| 2 | limits: problem -> language -> defaults (3s/128MB) | `services/judge.py` |
| 3 | testcases visible to all logged-in users; edit any logged-in user; delete admin-only | `routers/problems.py` |
| 4 | deleting a problem cascades to submissions/logs/audit | `services/problem_ops.py` |
| 5 | git history may be "complete first, iterate later" | (process note) |
| 6 | language registration never installs compilers | `services/language_ops.py` |
| 7 | rate limit 3/min is per user+problem | `services/submission_ops.py` |
| 8 | deleting a problem reverts submit_count / resolve_count | `services/problem_ops.py` |
| 9 | `/api/logs/access/` primary conditions may not both be empty (400) | `routers/logs.py` |

## Assignment Notes

- All API endpoints must use FastAPI's async interface (`async def`).
- Git commits follow [Conventional Commits](https://www.conventionalcommits.org/).

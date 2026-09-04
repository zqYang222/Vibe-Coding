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
app/            # FastAPI backend
  main.py       # Application entry point
  config.py     # Defaults (time/memory limits, paths) and settings
  models/       # Pydantic models (problem, submission, user)
  routers/      # API routers (problems, submissions, languages, auth, users, logs, ai)
  services/     # Business logic (auth, problem ops, judge)
  judge/        # Language registration & evaluation engine
frontend/       # Streamlit frontend
  app.py
data/           # Runtime data (problems are tracked; submissions/users/logs are not)
  problems/     # One JSON file per problem
  submissions/
  users/
  logs/
tests/          # pytest tests
```

## Quick Start

```bash
# Create a virtual environment
python -m venv .venv
# Activate it (Windows)
.venv\Scripts\activate
# Install dependencies
pip install -r requirements.txt
# Run the backend
uvicorn app.main:app --reload
# Run the frontend (in another terminal)
streamlit run frontend/app.py
```

The system auto-creates an initial admin account on startup:
username `admin`, password `admintestpassword`.

## Assignment Notes

- All API endpoints must use FastAPI's async interface (`async def`).
- Git commits follow [Conventional Commits](https://www.conventionalcommits.org/).

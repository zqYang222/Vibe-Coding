"""Global configuration and shared defaults for the OJ system."""

from pathlib import Path

# Project root directory (parent of the `app` package).
BASE_DIR = Path(__file__).resolve().parent.parent

# Runtime data storage directories.
DATA_DIR = BASE_DIR / "data"
PROBLEMS_DIR = DATA_DIR / "problems"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
USERS_DIR = DATA_DIR / "users"
LOGS_DIR = DATA_DIR / "logs"
JUDGE_LOGS_DIR = LOGS_DIR / "judge"
ACCESS_LOGS_DIR = LOGS_DIR / "access"

# Evaluation defaults (used when a problem/language does not override them).
# Per TA Q&A: priority is problem config -> language config -> these defaults.
DEFAULT_TIME_LIMIT = 3.0  # seconds
DEFAULT_MEMORY_LIMIT = 128  # MB

# Initial admin account created on startup.
INITIAL_ADMIN_USERNAME = "admin"
INITIAL_ADMIN_PASSWORD = "admintestpassword"

# Submission rate limit (TA Q&A: per user AND per problem).
SUBMIT_RATE_LIMIT = 3
SUBMIT_RATE_WINDOW_SECONDS = 60

# Session secret for the session-based login (Step 4).
import os

SESSION_SECRET = os.environ.get("OJ_SESSION_SECRET", "oj-local-dev-secret")

# Ensure runtime directories exist.
for _dir in (
    PROBLEMS_DIR,
    SUBMISSIONS_DIR,
    USERS_DIR,
    LOGS_DIR,
    JUDGE_LOGS_DIR,
    ACCESS_LOGS_DIR,
):
    _dir.mkdir(parents=True, exist_ok=True)

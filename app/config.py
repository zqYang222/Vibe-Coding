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

# Evaluation defaults (used when a problem/language does not override them).
DEFAULT_TIME_LIMIT = 3.0  # seconds
DEFAULT_MEMORY_LIMIT = 128  # MB

# Initial admin account created on startup.
INITIAL_ADMIN_USERNAME = "admin"
INITIAL_ADMIN_PASSWORD = "admintestpassword"

# Submission rate limit (Step 4): max submissions per window.
SUBMIT_RATE_LIMIT = 3
SUBMIT_RATE_WINDOW_SECONDS = 60

# Ensure runtime directories exist (created lazily at startup).
for _dir in (PROBLEMS_DIR, SUBMISSIONS_DIR, USERS_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

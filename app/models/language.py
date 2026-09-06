"""Pydantic models for languages (Step 2)."""

from typing import Optional

from pydantic import BaseModel


class LanguageModel(BaseModel):
    """Configuration of a supported language (api.md POST /api/languages/)."""

    name: str
    file_ext: str  # e.g. ".py", ".cpp"
    run_cmd: str  # e.g. "python3 {src}", "{exe}"
    compile_cmd: Optional[str] = None  # omitted for interpreted languages
    # Optional per-language limits; used only when the problem does not set
    # its own (TA Q&A: problem -> language -> system defaults).
    time_limit: Optional[float] = None
    memory_limit: Optional[int] = None

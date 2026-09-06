"""Pydantic models for submissions (Steps 2 & 3)."""

from pydantic import BaseModel


class SubmissionCreate(BaseModel):
    """Request payload of POST /api/submissions/."""

    problem_id: str
    language: str
    code: str

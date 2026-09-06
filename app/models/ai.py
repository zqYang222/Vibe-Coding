"""Pydantic models for the AI problem-generation module (Advance)."""

from typing import Optional

from pydantic import BaseModel


class ModelConfigPayload(BaseModel):
    provider_url: str
    model: str
    api_key: str
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    price_unit: Optional[int] = None  # tokens per price unit, e.g. 1000000


class ProblemTaskCreate(BaseModel):
    requirement: str
    problem_id: Optional[str] = None

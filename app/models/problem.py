"""Pydantic models for OJ problems (Step 1)."""

from typing import List, Optional

from pydantic import BaseModel


class Case(BaseModel):
    """A sample or test case: one input / expected output pair."""

    input: str
    output: str


class ProblemModel(BaseModel):
    """Full problem configuration, stored as one JSON file per problem."""

    # Required fields (api.md, Step 1).
    id: str
    title: str
    description: str
    input_description: str
    output_description: str
    samples: List[Case]
    constraints: str
    testcases: List[Case]

    # Optional fields default to their natural empty values:
    # str -> "", list -> [] (api.md "默认字段需要返回本类型默认值").
    hint: str = ""
    source: str = ""
    tags: List[str] = []
    author: str = ""
    difficulty: str = ""

    # Limits stay None here instead of baking in 3s/128MB: per TA Q&A,
    # limits are resolved at judging time in the order
    # problem config -> language config -> system defaults (3s / 128MB).
    time_limit: Optional[float] = None
    memory_limit: Optional[int] = None

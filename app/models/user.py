"""Pydantic models for users (Step 4)."""

from pydantic import BaseModel


class LoginPayload(BaseModel):
    username: str
    password: str


class RegisterPayload(BaseModel):
    username: str
    password: str


class AdminCreatePayload(BaseModel):
    username: str
    password: str


class RoleUpdatePayload(BaseModel):
    role: str

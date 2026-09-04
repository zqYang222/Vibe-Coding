"""FastAPI application entry point for the Online Judge system."""

from fastapi import FastAPI

app = FastAPI(title="Online Judge", version="0.1.0")


@app.get("/")
async def root():
    """Health-check endpoint."""
    return {"code": 200, "msg": "success", "data": {"service": "oj"}}

# FastAPI Skill-Checker App

This module exposes a FastAPI application and a router you can mount into your existing app.

Examples

Mount router into your existing FastAPI app:

```python
from fastapi import FastAPI
from app.api.router import router as skill_checker_router

app = FastAPI()
app.include_router(skill_checker_router, prefix="/skill-checker", tags=["skill-checker"])
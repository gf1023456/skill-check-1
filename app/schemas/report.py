from pydantic import BaseModel
from typing import Any, List, Optional

class ManifestModel(BaseModel):
    name: str
    version: Optional[str]
    entrypoint: dict
    triggers: Optional[List[str]] = []
    tests: Optional[List[dict]] = []

class ActionResult(BaseModel):
    id: str
    ok: bool
    status: Optional[int]
    error: Optional[str]
    reasons: Optional[List[str]]
    resp_snippet: Optional[str]

class ReportModel(BaseModel):
    skill: Optional[str]
    version: Optional[str]
    static: Any
    deterministic_tests: List[Any]
    llm_plan_raw: Optional[str]
    plan_results: Any
    trace: dict
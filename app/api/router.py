from pathlib import Path
from typing import Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..core.config import settings
from ..services.skill_manager import SkillManager

router = APIRouter()
STORAGE = Path(settings.storage_dir)
STORAGE.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_skill(file: UploadFile = File(...)):
    """Store an uploaded skill archive and return its opaque identifier."""
    skill_id = str(uuid.uuid4())
    skill_dir = STORAGE / skill_id
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.zip").write_bytes(await file.read())
    return JSONResponse({"skill_id": skill_id, "message": "uploaded"})


@router.post("/start/{skill_id}")
async def start_check(skill_id: str, background_tasks: BackgroundTasks, baseline_id: Optional[str] = None):
    if not (STORAGE / skill_id / "skill.zip").is_file():
        raise HTTPException(status_code=404, detail="skill not found")
    manager = SkillManager(storage_root=STORAGE)
    background_tasks.add_task(manager.run_check_for_skill, skill_id, baseline_id)
    return JSONResponse({"skill_id": skill_id, "status": "started", "baseline": baseline_id})


@router.get("/status/{skill_id}")
async def status(skill_id: str):
    result = SkillManager(storage_root=STORAGE).get_status(skill_id)
    if result is None:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse(result)


@router.get("/report/{skill_id}")
async def report(skill_id: str):
    result = SkillManager(storage_root=STORAGE).get_report(skill_id)
    if result is None:
        raise HTTPException(status_code=404, detail="report not found or check not finished")
    return JSONResponse(result)

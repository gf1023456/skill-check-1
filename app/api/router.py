from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
import uuid
import os
from ..core.config import settings
from ..services.skill_manager import SkillManager

router = APIRouter()

STORAGE = Path(settings.storage_dir)
STORAGE.mkdir(parents=True, exist_ok=True)

@router.post("/upload")
async def upload_skill(file: UploadFile = File(...)):
    # Save uploaded zip into storage with generated id
    sid = str(uuid.uuid4())
    skill_dir = STORAGE / sid
    skill_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    zip_path = skill_dir / "skill.zip"
    zip_path.write_bytes(content)
    return JSONResponse({"skill_id": sid, "message": "uploaded"})



@router.post("/start/{skill_id}")
async def start_check(skill_id: str, background_tasks: BackgroundTasks, baseline_id: str = None):
    ...
    manager = SkillManager(storage_root=STORAGE)
    background_tasks.add_task(manager.run_check_for_skill, skill_id, baseline_id)
    return JSONResponse({"skill_id": skill_id, "status": "started", "baseline": baseline_id})


@router.get("/status/{skill_id}")
async def status(skill_id: str):
    manager = SkillManager(storage_root=STORAGE)
    st = manager.get_status(skill_id)
    if st is None:
        raise HTTPException(status_code=404, detail="not found")
    return JSONResponse(st)

@router.get("/report/{skill_id}")
async def report(skill_id: str):
    manager = SkillManager(storage_root=STORAGE)
    rep = manager.get_report(skill_id)
    if rep is None:
        raise HTTPException(status_code=404, detail="report not found or check not finished")
    return JSONResponse(rep)
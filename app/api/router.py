from pathlib import Path
from typing import Optional
import logging
import uuid
import json

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from ..core.config import settings
from ..agent.agent import SkillCheckerAgent

logger = logging.getLogger(__name__)
router = APIRouter()
STORAGE = Path(settings.storage_dir)
STORAGE.mkdir(parents=True, exist_ok=True)

# Global agent instance (initialized lazily)
_agent: Optional[SkillCheckerAgent] = None


def get_agent() -> SkillCheckerAgent:
    """Get or create the global agent instance."""
    global _agent
    if _agent is None:
        _agent = SkillCheckerAgent()
    return _agent


@router.post("/upload")
async def upload_skill(file: UploadFile = File(...)):
    """Store an uploaded skill archive and return its opaque identifier."""
    # 使用短 UUID (8字符) 避免 Windows 路径过长
    skill_id = str(uuid.uuid4())[:8]
    skill_dir = STORAGE / skill_id
    skill_dir.mkdir(parents=True)
    content = await file.read()
    (skill_dir / "skill.zip").write_bytes(content)
    logger.info(f"[{skill_id}] ZIP上传完成: filename={file.filename}, size={len(content)} bytes")
    return JSONResponse({"skill_id": skill_id, "message": "uploaded"})


@router.post("/start/{skill_id}")
async def start_check(skill_id: str, background_tasks: BackgroundTasks, baseline_id: Optional[str] = None):
    if not (STORAGE / skill_id / "skill.zip").is_file():
        logger.error(f"[{skill_id}] 启动验证失败: ZIP文件不存在")
        raise HTTPException(status_code=404, detail="skill not found")
    
    agent = get_agent()
    skill_zip_path = str(STORAGE / skill_id / "skill.zip")
    
    # Run agent in background
    background_tasks.add_task(_run_agent_background, agent, skill_id, skill_zip_path)
    
    logger.info(f"[{skill_id}] Agent验证任务已提交后台执行")
    return JSONResponse({"skill_id": skill_id, "status": "started", "baseline": baseline_id})


async def _run_agent_background(agent: SkillCheckerAgent, skill_id: str, skill_zip_path: str):
    """Run agent in background and save results."""
    import asyncio
    
    try:
        logger.info(f"[{skill_id}] Agent后台任务开始")
        
        # Run the agent
        result = await agent.run(skill_id, skill_zip_path)
        
        # Save report
        report_path = STORAGE / skill_id / "report.json"
        report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Save status
        status_path = STORAGE / skill_id / "status.json"
        status_path.write_text(json.dumps({"status": "done"}, ensure_ascii=False), encoding="utf-8")
        
        logger.info(f"[{skill_id}] Agent后台任务完成，报告已保存")
        
    except Exception as e:
        logger.error(f"[{skill_id}] Agent后台任务失败: {e}", exc_info=True)
        
        # Save error status
        status_path = STORAGE / skill_id / "status.json"
        status_path.write_text(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False), encoding="utf-8")


@router.get("/status/{skill_id}")
async def status(skill_id: str):
    status_path = STORAGE / skill_id / "status.json"
    if not status_path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    
    try:
        result = json.loads(status_path.read_text(encoding="utf-8"))
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[{skill_id}] 读取状态失败: {e}")
        raise HTTPException(status_code=500, detail="failed to read status")


@router.get("/report/{skill_id}")
async def report(skill_id: str):
    report_path = STORAGE / skill_id / "report.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="report not found or check not finished")
    
    try:
        result = json.loads(report_path.read_text(encoding="utf-8"))
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"[{skill_id}] 读取报告失败: {e}")
        raise HTTPException(status_code=500, detail="failed to read report")

from fastapi import FastAPI

from app.api.router import router as checker_router
import logging
import os
import sys
from dotenv import load_dotenv
# 显式加载项目根目录的 .env 文件
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
import uvicorn
# 必须在任何其他代码之前设置
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 配置全局日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# 修复 Windows 控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
def create_app() -> FastAPI:
    app = FastAPI(title="Skill Checker")
    app.include_router(checker_router, prefix="/skill-checker", tags=["skill-checker"])
    return app


app = create_app()
# ==================== 启动服务 ====================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8098,
        reload=True
    )
from fastapi import FastAPI

from app.api.router import router as checker_router


def create_app() -> FastAPI:
    app = FastAPI(title="Skill Checker")
    app.include_router(checker_router, prefix="/skill-checker", tags=["skill-checker"])
    return app


app = create_app()

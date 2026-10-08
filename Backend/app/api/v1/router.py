from fastapi import APIRouter

from app.api.v1 import auth, doubts, notebook, papers, practice, progress, study_plan, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(practice.router)
api_router.include_router(progress.router)
api_router.include_router(papers.router)
api_router.include_router(doubts.router)
api_router.include_router(notebook.router)
api_router.include_router(study_plan.router)


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

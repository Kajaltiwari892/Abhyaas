from fastapi import APIRouter

from app.api.v1 import auth, practice, progress, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(practice.router)
api_router.include_router(progress.router)


@api_router.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

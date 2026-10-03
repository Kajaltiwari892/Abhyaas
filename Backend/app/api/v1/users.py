from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import DatabaseSession, get_current_user
from app.models.auth import User
from app.schemas.auth import UserPreferencesRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=UserResponse)
async def current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me/preferences", response_model=UserResponse)
async def update_preferences(
    payload: UserPreferencesRequest, user: CurrentUser, db: DatabaseSession
) -> UserResponse:
    # The bearer session owns this row. No client-supplied account IDs are accepted.
    user.target_academy = payload.target_academy
    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)

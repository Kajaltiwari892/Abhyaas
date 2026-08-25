from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.auth import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("/me", response_model=UserResponse)
async def current_user(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.auth import User

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]
DatabaseSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: BearerCredentials,
    db: DatabaseSession,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError as error:
        raise unauthorized from error

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user

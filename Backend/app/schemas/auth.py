from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Name is too short")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(character.isalpha() for character in value):
            raise ValueError("Password must contain a letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain a number")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: EmailStr
    is_verified: bool
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(character.isalpha() for character in value):
            raise ValueError("Password must contain a letter")
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain a number")
        return value

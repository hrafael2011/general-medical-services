from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: str
    name: str
    email: str
    role: str
    active: bool
    must_change_password: bool
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


class CreateEncargadoRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    temporary_password: str | None = Field(default=None, min_length=10)
    permissions: list[str] = Field(default_factory=list)


class TemporaryPasswordResponse(BaseModel):
    user: UserRead
    temporary_password: str


class ResetPasswordRequest(BaseModel):
    temporary_password: str | None = Field(default=None, min_length=10)


class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = Field(default=None, pattern=r"^(admin|encargado)$")
    active: bool | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

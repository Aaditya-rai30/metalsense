from typing import Optional

from fastapi import (
    APIRouter,
    Header,
    Request,
)
from pydantic import BaseModel, EmailStr

from security.rate_limit import rate_limit_auth

from services.auth_service import (
    authenticate_user,
    create_user,
    get_current_user,
    logout,
)


router = APIRouter()


class Signup(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    account_type: str
    organization: Optional[str] = ""
    role: str
    institution: Optional[str] = ""
    research_area: Optional[str] = ""


class Login(BaseModel):
    email: EmailStr
    password: str


# ============================================================
# SIGNUP
# ============================================================

@router.post("/signup")
async def signup(
    payload: Signup,
    request: Request,
):
    rate_limit_auth(request)

    return await create_user(
        payload.model_dump()
    )


# ============================================================
# LOGIN
# ============================================================

@router.post("/login")
async def login(
    payload: Login,
    request: Request,
):
    rate_limit_auth(request)

    return await authenticate_user(
        payload.email,
        payload.password,
    )


# ============================================================
# LOGOUT
# ============================================================

@router.post("/logout")
async def logout_user(
    authorization: Optional[str] = Header(None),
):
    return await logout(
        authorization
    )

# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me")
async def me(
    authorization: Optional[str] = Header(
        None
    ),
):
    return await get_current_user(
        authorization
    )
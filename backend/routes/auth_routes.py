from typing import Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel, EmailStr

from services.auth_service import (
    authenticate_user,
    create_user,
    get_current_user,
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


@router.post("/signup")
async def signup(payload: Signup):
    return await create_user(
        payload.model_dump()
    )


@router.post("/login")
async def login(payload: Login):
    return await authenticate_user(
        payload.email,
        payload.password,
    )


@router.get("/me")
async def me(
    authorization: Optional[str] = Header(None),
):
    return await get_current_user(
        authorization
    )

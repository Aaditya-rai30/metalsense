import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException

from database import db


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        120000,
    ).hex()


async def create_user(data: dict):
    if len(data["password"]) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
        )

    if (
        data["account_type"]
        in [
            "Company / Organization",
            "Government / Public Organization",
        ]
        and not data.get("organization")
    ):
        raise HTTPException(
            status_code=400,
            detail="Organization name is required for this account type",
        )

    if not data.get("organization"):
        if "Researcher" in data["account_type"]:
            data["organization"] = "Independent Researcher"
        else:
            data["organization"] = "No Organization"

    email = data["email"].lower()

    existing = await db.users.find_one(
        {"email": email}
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    salt = secrets.token_hex(16)

    user = {
        "user_id": str(uuid.uuid4()),
        "full_name": data["full_name"],
        "email": email,
        "account_type": data["account_type"],
        "organization": data.get("organization", ""),
        "role": data["role"],
        "institution": data.get("institution", ""),
        "research_area": data.get("research_area", ""),
        "created_at": now_iso(),
        "password_hash": password_hash(
            data["password"],
            salt,
        ),
        "salt": salt,
    }

    await db.users.insert_one(user)

    return await issue_session(user)


async def authenticate_user(
    email: str,
    password: str,
):
    user = await db.users.find_one(
        {
            "email": email.lower()
        }
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    stored_hash = user.get(
        "password_hash",
        "",
    )

    salt = user.get(
        "salt",
        "",
    )

    if password_hash(password, salt) != stored_hash:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    return await issue_session(user)


async def issue_session(user: dict):
    token = secrets.token_urlsafe(32)

    await db.sessions.insert_one(
        {
            "token": token,
            "user_id": user["user_id"],
            "created_at": now_iso(),
        }
    )

    public_user = {
        key: value
        for key, value in user.items()
        if key not in [
            "_id",
            "password_hash",
            "salt",
        ]
    }

    return {
        "token": token,
        "user": public_user,
    }


async def get_current_user(
    authorization: str | None,
):
    if (
        not authorization
        or not authorization.startswith("Bearer ")
    ):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    token = authorization[7:]

    session = await db.sessions.find_one(
        {
            "token": token
        },
        {
            "_id": 0
        },
    )

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session expired",
        )

    user = await db.users.find_one(
        {
            "user_id": session["user_id"]
        },
        {
            "_id": 0,
            "password_hash": 0,
            "salt": 0,
        },
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user

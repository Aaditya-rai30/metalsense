import hashlib
import secrets
import uuid

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from database import db


# ============================================================
# SESSION CONFIGURATION
# ============================================================

SESSION_TTL_HOURS = 24


# ============================================================
# TIME HELPERS
# ============================================================

def now_utc() -> datetime:
    return datetime.now(
        timezone.utc
    )


def now_iso() -> str:
    return now_utc().isoformat()


def session_expiry() -> str:
    return (
        now_utc()
        + timedelta(
            hours=SESSION_TTL_HOURS
        )
    ).isoformat()


# ============================================================
# PASSWORD HASHING
# ============================================================

def password_hash(
    password: str,
    salt: str,
) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt.encode(),
        120000,
    ).hex()


# ============================================================
# CREATE USER
# ============================================================

async def create_user(
    data: dict,
):
    if len(data["password"]) < 8:
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least "
                "8 characters"
            ),
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
            detail=(
                "Organization name is required "
                "for this account type"
            ),
        )

    if not data.get("organization"):

        if "Researcher" in data["account_type"]:
            data["organization"] = (
                "Independent Researcher"
            )

        else:
            data["organization"] = (
                "No Organization"
            )

    email = data["email"].lower()

    existing = await db.users.find_one(
        {
            "email": email
        }
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "An account with this email "
                "already exists"
            ),
        )

    salt = secrets.token_hex(16)

    user = {
        "user_id":
            str(uuid.uuid4()),

        "full_name":
            data["full_name"],

        "email":
            email,

        "account_type":
            data["account_type"],

        "organization":
            data.get(
                "organization",
                "",
            ),

        "role":
            data["role"],

        "institution":
            data.get(
                "institution",
                "",
            ),

        "research_area":
            data.get(
                "research_area",
                "",
            ),

        "created_at":
            now_iso(),

        "password_hash":
            password_hash(
                data["password"],
                salt,
            ),

        "salt":
            salt,
    }

    await db.users.insert_one(
        user
    )

    return await issue_session(
        user
    )


# ============================================================
# AUTHENTICATE USER
# ============================================================

async def authenticate_user(
    email: str,
    password: str,
):
    user = await db.users.find_one(
        {
            "email":
                email.lower()
        }
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail=(
                "Incorrect email or password"
            ),
        )

    stored_hash = user.get(
        "password_hash",
        "",
    )

    salt = user.get(
        "salt",
        "",
    )

    if (
        password_hash(
            password,
            salt,
        )
        != stored_hash
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Incorrect email or password"
            ),
        )

    return await issue_session(
        user
    )


# ============================================================
# ISSUE SESSION
# ============================================================

async def issue_session(
    user: dict,
):
    token = secrets.token_urlsafe(
        32
    )

    created_at = now_iso()

    expires_at = session_expiry()

    await db.sessions.insert_one(
        {
            "token":
                token,

            "user_id":
                user["user_id"],

            "created_at":
                created_at,

            "expires_at":
                expires_at,
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
        "token":
            token,

        "expires_at":
            expires_at,

        "user":
            public_user,
    }


# ============================================================
# CURRENT USER
# ============================================================

async def get_current_user(
    authorization: str | None,
):
    if (
        not authorization
        or not authorization.startswith(
            "Bearer "
        )
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required"
            ),
        )

    token = (
        authorization[7:]
        .strip()
    )

    if not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required"
            ),
        )

    session = await db.sessions.find_one(
        {
            "token":
                token
        },
        {
            "_id":
                0
        },
    )

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session expired",
        )

    # --------------------------------------------------------
    # SESSION EXPIRATION
    # --------------------------------------------------------

    expires_at_raw = session.get(
        "expires_at"
    )

    if not expires_at_raw:
        # Legacy session created before expiration support.
        # Revoke it rather than treating a non-expiring token
        # as permanently valid.
        await db.sessions.delete_one(
            {
                "token":
                    token
            }
        )

        raise HTTPException(
            status_code=401,
            detail="Session expired",
        )

    try:
        expires_at = datetime.fromisoformat(
            expires_at_raw
        )

        if (
            expires_at.tzinfo
            is None
        ):
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

    except (
        TypeError,
        ValueError,
    ):

        await db.sessions.delete_one(
            {
                "token":
                    token
            }
        )

        raise HTTPException(
            status_code=401,
            detail="Invalid session",
        )

    # --------------------------------------------------------
    # EXPIRED SESSION
    # --------------------------------------------------------

    if expires_at <= now_utc():

        await db.sessions.delete_one(
            {
                "token":
                    token
            }
        )

        raise HTTPException(
            status_code=401,
            detail="Session expired",
        )

    # --------------------------------------------------------
    # USER
    # --------------------------------------------------------

    user = await db.users.find_one(
        {
            "user_id":
                session["user_id"]
        },
        {
            "_id":
                0,

            "password_hash":
                0,

            "salt":
                0,
        },
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return user


# ============================================================
# LOGOUT
# ============================================================

async def logout(
    authorization: str | None,
):
    if (
        not authorization
        or not authorization.startswith(
            "Bearer "
        )
    ):
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required"
            ),
        )

    token = (
        authorization[7:]
        .strip()
    )

    if not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "Authentication required"
            ),
        )

    result = await db.sessions.delete_one(
        {
            "token":
                token
        }
    )

    if not result.deleted_count:
        raise HTTPException(
            status_code=401,
            detail="Invalid session",
        )

    return {
        "message":
            "Logged out successfully"
    }


# ============================================================
# SESSION CLEANUP
# ============================================================

async def cleanup_expired_sessions():
    """
    Remove expired sessions from MongoDB.

    This can later be called periodically using a scheduled
    background task or deployment-level scheduler.
    """

    result = await db.sessions.delete_many(
        {
            "expires_at": {
                "$lte":
                    now_iso()
            }
        }
    )

    return {
        "deleted_sessions":
            result.deleted_count
    }
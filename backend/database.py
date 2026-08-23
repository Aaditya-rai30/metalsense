from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URL, DB_NAME


client = AsyncIOMotorClient(MONGO_URL)

db = client[DB_NAME]


async def ensure_indexes():
    await db.sessions.create_index(
        "expires_at",
        expireAfterSeconds=0,
    )


async def close_database():
    client.close()
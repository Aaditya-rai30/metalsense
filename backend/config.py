import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    raise RuntimeError(
        "MONGO_URL is not configured. "
        "Add your MongoDB Atlas connection string to backend/.env"
    )


DB_NAME = os.getenv(
    "DB_NAME",
    "metalsense",
)

STANDARD_FILE = BASE_DIR / "standard.csv"

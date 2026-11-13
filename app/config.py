import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
if APP_ENV not in {"development", "test", "production"}:
    raise ValueError("APP_ENV must be development, test, or production")

database_url = os.getenv("DATABASE_URL")
if APP_ENV == "production" and not database_url:
    raise RuntimeError("DATABASE_URL must be configured in production")
DATABASE_URL = database_url or f"sqlite:///{BASE_DIR / 'asama.db'}"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    if APP_ENV == "production":
        raise RuntimeError("JWT_SECRET_KEY must be configured in production")
    JWT_SECRET_KEY = secrets.token_urlsafe(32)
if APP_ENV == "production" and len(JWT_SECRET_KEY.encode("utf-8")) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes in production")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

seed_demo_data = os.getenv("SEED_DEMO_DATA")
if seed_demo_data is None:
    SEED_DEMO_DATA = APP_ENV == "development"
elif seed_demo_data.strip().lower() in {"true", "1", "yes"}:
    SEED_DEMO_DATA = True
elif seed_demo_data.strip().lower() in {"false", "0", "no"}:
    SEED_DEMO_DATA = False
else:
    raise ValueError("SEED_DEMO_DATA must be a boolean value")
if APP_ENV == "production" and SEED_DEMO_DATA:
    raise ValueError("SEED_DEMO_DATA cannot be enabled in production")

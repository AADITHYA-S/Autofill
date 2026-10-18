from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException

from backend.database.mongodb import get_database
from backend.security.encryption import encrypt_text
from backend.security.hmac_utils import normalize_phone_number, tokenise
from backend.settings import get_settings
from backend.repositories.patient_profiles import initialize_patient_profile

def create_access_token(user_id: str | ObjectId, expires_minutes: int = 30) -> str:
    settings = get_settings()
    secret = settings.jwt_secret_key or "development-secret-change-me"
    algorithm = settings.jwt_algorithm or "HS256"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, secret, algorithm=algorithm)


def register_user(phone: str, password: str, consent_given: bool = False) -> ObjectId:
    if not phone or not password:
        raise ValueError("Phone and password are required")

    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        raise ValueError("Enter a valid 10-digit phone number")
    phone_hash = tokenise(normalized_phone)
    database = get_database()

    if database.users.find_one({"phone_hash": phone_hash}):
        raise ValueError("A user with this phone number already exists")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = datetime.now(timezone.utc)
    user_record = {
        "phone_hash": phone_hash,
        "phone_enc": encrypt_text(normalized_phone),
        "password_hash": password_hash,
        "role": "patient",
        "consent_given": bool(consent_given),
        "consent_timestamp": now,
        "is_active": True,
        "failed_login_attempts": 0,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }
    user_record["_id"] = ObjectId()
    result = database.users.insert_one(user_record)
    user_id = result.inserted_id or user_record["_id"]

    try:
        initialize_patient_profile(user_id, normalized_phone)
    except Exception:
        database.users.delete_one({"_id": user_id})
        raise

    return user_id


def login_user(phone: str, password: str) -> str:
    if not phone or not password:
        raise HTTPException(status_code=401, detail="Phone and password are required")

    normalized_phone = normalize_phone_number(phone)
    if not normalized_phone:
        raise HTTPException(
            status_code=401,
            detail="Invalid phone or password",
        )
    phone_hash = tokenise(normalized_phone)
    database = get_database()
    user = database.users.find_one({"phone_hash": phone_hash})
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    stored_hash = user.get("password_hash")
    if not isinstance(stored_hash, str):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    user_id = user.get("_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    now = datetime.now(timezone.utc)
    database.users.update_one(
        {"_id": user_id},
        {"$set": {"last_login_at": now, "updated_at": now}},
    )
    return create_access_token(user_id)

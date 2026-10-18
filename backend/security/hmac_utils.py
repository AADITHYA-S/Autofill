from __future__ import annotations

import hashlib
import hmac
import re

from backend.settings import get_settings


def normalize_phone_number(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")

    if len(digits) == 10:
        return digits

    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]

    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]

    return ""


def tokenise(value: str) -> str:
    secret = get_settings().hmac_salt_secret
    if not secret:
        raise RuntimeError("HMAC_SALT_SECRET is required")
    return hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()
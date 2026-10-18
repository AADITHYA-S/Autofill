from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from backend.database.mongodb import get_database
# from backend.security.encryption import ActiveDek, encrypt_text
from backend.security.hmac_utils import normalize_phone_number, tokenise
from backend.repositories.profile_normalizer import parse_address,parse_name

from backend.security.encryption import ActiveDek, encrypt_text, get_active_dek
from backend.security.decryption import decrypt_field


def _normalize_gender(value: object) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    if lowered in {"male", "m"}:
        return "MALE"
    if lowered in {"female", "f"}:
        return "FEMALE"
    if lowered == "other":
        return "OTHER"
    if lowered == "not specified":
        return "Not specified"
    return normalized


def _value(fields: dict, *names: str):
    for name in names:
        item = fields.get(name)
        if isinstance(item, dict) and item.get("value") is not None:
            return item["value"]
    return None


def _encode_if_present(update: dict, field_name: str, value: object) -> None:
    if value is not None:
        update[field_name] = encrypt_text(str(value))


def build_profile_update(fields: dict, dek: ActiveDek) -> dict:
    update: dict = {"dek_id": dek.id, "updated_at": datetime.now(timezone.utc)}

    # #name
    # raw_name=_value(fields,"full_name","name")
    # name_parts = (parse_name(str(raw_name)) if raw_name else {})

    raw_name = _value(fields, "full_name", "name")
    raw_name = str(raw_name).strip() if raw_name is not None else ""
    name_parts = parse_name(raw_name) if raw_name else {}

    raw_address=_value(fields,"address")

    address_parts=(parse_address(str(raw_address)) if raw_address else {})

    encrypted_fields = {
        "name_enc": name_parts.get("full_name"),
        "first_name_enc": name_parts.get("first_name"),
        "middle_name_enc": name_parts.get("middle_name"),
        "last_name_enc": name_parts.get("last_name"),
        
        "dob_enc": _value(fields, "date_of_birth"),
        # Keep original complete address
        "address_enc": address_parts.get("full_address"),

        # Structured address
        "house_number_enc": address_parts.get("house_number"),
        "street_enc": address_parts.get("street"),
        "locality_enc": address_parts.get("locality"),
        "city_enc": address_parts.get("city"),
        "state_enc": address_parts.get("state"),
        "pincode_enc": address_parts.get("pincode"),

        "guardian_name_enc": _value(fields, "father_or_husband_name", "father_name", "relative_name", "mother_name", "spouse_name", "policy_holder_name"),
        "place_of_birth_enc": _value(fields, "place_of_birth"),
        "insurance_details_enc": _value(fields, "insurance_details"),
    }
    for field_name, value in encrypted_fields.items():
        _encode_if_present(update, field_name, value)

    for target in ("gender", "blood_group", "year_of_birth", "nationality"):
        value = _value(fields, target)
        if value is not None:
            normalized_value = _normalize_gender(value) if target == "gender" else value
            if normalized_value is not None:
                update[target] = normalized_value

    # phone_value = _value(fields, "mobile_number", "phone_number")
    # if phone_value is not None:
    #     normalized_phone = normalize_phone_number(str(phone_value))
    #     update["phone_enc"] = encrypt_text(normalized_phone)
    #     update["phone_hash"] = tokenise(normalized_phone)
    phone_value = _value(fields, "mobile_number", "phone_number")

    if phone_value is not None:
        normalized_phone = normalize_phone_number(str(phone_value))
        if normalized_phone:
            update["phone_enc"] = encrypt_text(normalized_phone)
            update["phone_hash"] = tokenise(normalized_phone)

    identifier_enc_map = {
        "aadhaar_enc": "aadhaar_number",
        "pan_enc": "pan_number",
        "voter_id_enc": "epic_number",
        "driving_licence_enc": "driving_licence_number",
        "passport_enc": "passport_number",
        "birth_reg_enc": "registration_number",
        "health_insurance_enc": "member_id",
    }
    for target, source in identifier_enc_map.items():
        value = _value(fields, source)
        _encode_if_present(update, target, value)

    token_fields = {
        "aadhaar_token": "aadhaar_number",
        "pan_token": "pan_number",
        "voter_id_token": "epic_number",
        "driving_licence_token": "driving_licence_number",
        "passport_token": "passport_number",
        "birth_reg_token": "registration_number",
        "health_insurance_token": "member_id",
    }
    for target, source in token_fields.items():
        value = _value(fields, source)
        if value is not None:
            update[target] = tokenise(str(value))

    return update


def get_profile_id(user_id: ObjectId) -> ObjectId:
    collection = get_database().patient_profiles
    existing = collection.find_one({"user_id": user_id}, {"_id": 1})
    return existing["_id"] if existing else ObjectId()


def initialize_patient_profile(user_id: ObjectId, phone: str) -> ObjectId:
    collection = get_database().patient_profiles

    existing = collection.find_one({"user_id": user_id}, {"_id": 1})
    if existing:
        return existing["_id"]

    dek = get_active_dek()
    now = datetime.now(timezone.utc)
    normalized_phone = normalize_phone_number(phone)

    if not normalized_phone:
        raise ValueError("A valid phone number is required")

    profile = {
        "user_id": user_id,
        "name_enc": encrypt_text(""),
        "phone_enc": encrypt_text(normalized_phone),
        "phone_hash": tokenise(normalized_phone),
        "dek_id": dek.id,
        "created_at": now,
        "updated_at": now,
    }

    result = collection.insert_one(profile)
    return result.inserted_id

def upsert_patient_profile(user_id: ObjectId, profile_id: ObjectId, fields: dict, dek: ActiveDek) -> ObjectId:
    collection = get_database().patient_profiles
    update = build_profile_update(fields, dek)
    update["user_id"] = user_id
    # if "name_enc" not in update and not collection.find_one({"user_id": user_id}, {"_id": 1}):
    #     raise RuntimeError("A new patient profile requires an extracted name")

    existing = collection.find_one(
        {"user_id": user_id},
        {"_id": 1, "name_enc": 1},
    )

    if "name_enc" not in update:
        if existing is None:
            raise RuntimeError("A new patient profile requires an extracted name")

        stored_name = decrypt_field(existing.get("name_enc"))
        if not stored_name.strip():
            raise RuntimeError("An extracted name is required to complete the patient profile")

        
    collection.update_one(
        {"user_id": user_id},
        {"$set": update, "$setOnInsert": {"_id": profile_id, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return profile_id
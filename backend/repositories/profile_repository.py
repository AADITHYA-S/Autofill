from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from backend.database.mongodb import get_database
from backend.security.encryption import encrypt_text
from backend.security.hmac_utils import normalize_phone_number, tokenise
from backend.security.decryption import decrypt_field


class ProfileRepository:
    """
    Repository for the authenticated user's identity profile.

    MongoDB keeps sensitive values encrypted and stores deterministic
    HMAC tokens only where they are required for lookup/deduplication.
    The API receives only the decrypted profile representation.
    """

    ENCRYPTED_FIELDS = {
        "name": "name_enc",
        "first_name": "first_name_enc",
        "middle_name": "middle_name_enc",
        "last_name": "last_name_enc",
        "dob": "dob_enc",
        "address": "address_enc",
        "house_number": "house_number_enc",
        "street": "street_enc",
        "locality": "locality_enc",
        "city": "city_enc",
        "state": "state_enc",
        "pincode": "pincode_enc",
        "phone": "phone_enc",
        "email":"email_enc",
        "guardian_name": "guardian_name_enc",
        "place_of_birth": "place_of_birth_enc",
        "insurance_details": "insurance_details_enc",
        "aadhaar_number": "aadhaar_enc",
        "pan_number": "pan_enc",
        "driving_licence_number": "driving_licence_enc",
        "voter_id": "voter_id_enc",
        "passport_number": "passport_enc",
        "birth_registration_number": "birth_reg_enc",
        "health_insurance": "health_insurance_enc",
    }

    TOKEN_FIELDS = {
        "phone": "phone_hash",
        "aadhaar_number": "aadhaar_token",
        "pan_number": "pan_token",
        "driving_licence_number": "driving_licence_token",
        "voter_id": "voter_id_token",
        "passport_number": "passport_token",
        "birth_registration_number": "birth_reg_token",
        "health_insurance": "health_insurance_token",
    }

    PLAIN_FIELDS = {
        "gender": "gender",
        "blood_group": "blood_group",
        "year_of_birth": "year_of_birth",
        "nationality": "nationality",
    }

    # MongoDB requires name_enc to exist. It therefore cannot be
    # individually removed without making the profile invalid.
    REQUIRED_DB_FIELDS = {"name"}

    def __init__(self):
        self.collection = get_database().patient_profiles

    @staticmethod
    def _object_id(user_id) -> ObjectId:
        if isinstance(user_id, ObjectId):
            return user_id
        try:
            return ObjectId(str(user_id))
        except Exception as exc:
            raise ValueError("Invalid user id") from exc

    def _find_document(self, user_id):
        oid = self._object_id(user_id)
        profile = self.collection.find_one({"user_id": oid})

        if not profile:
            raise ValueError("Identity profile not found")

        return profile

    def get_by_user_id(self, user_id):
        profile = self._find_document(user_id)
        return self._to_profile_response(profile)

    def _to_profile_response(self, profile):
        """
        Return every user-facing field supported by the current
        patient_profiles schema. Internal identifiers, HMAC tokens,
        DEK IDs and file-storage keys are intentionally not exposed.
        """

        def dec(db_field):
            value = profile.get(db_field)
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            return decrypt_field(value)

        def plain(db_field):
            value = profile.get(db_field)
            if value is None:
                return ""
            return str(value)

        return {
            "id": str(profile["_id"]),
            "user_id": str(profile["user_id"]),

            "name": dec("name_enc"),
            "first_name": dec("first_name_enc"),
            "middle_name": dec("middle_name_enc"),
            "last_name": dec("last_name_enc"),

            "dob": dec("dob_enc"),
            "gender": plain("gender"),
            "year_of_birth": plain("year_of_birth"),
            "blood_group": plain("blood_group"),
            "nationality": plain("nationality"),

            "address": dec("address_enc"),
            "house_number": dec("house_number_enc"),
            "street": dec("street_enc"),
            "locality": dec("locality_enc"),
            "city": dec("city_enc"),
            "state": dec("state_enc"),
            "pincode": dec("pincode_enc"),

            "phone": dec("phone_enc"),
            "email": dec("email_enc"),
            "guardian_name": dec("guardian_name_enc"),
            "place_of_birth": dec("place_of_birth_enc"),

            "aadhaar_number": dec("aadhaar_enc"),
            "pan_number": dec("pan_enc"),
            "voter_id": dec("voter_id_enc"),
            "passport_number": dec("passport_enc"),
            "driving_licence_number": dec("driving_licence_enc"),
            "birth_registration_number": dec("birth_reg_enc"),

            "health_insurance": dec("health_insurance_enc"),
            "insurance_details": dec("insurance_details_enc"),
        }

    @staticmethod
    def _normalise_plain(field: str, value):
        if value is None:
            return None

        value = str(value).strip()

        if field == "gender":
            lowered = value.lower()
            if lowered in {"male", "m"}:
                return "MALE"
            if lowered in {"female", "f"}:
                return "FEMALE"
            if lowered == "other":
                return "OTHER"
            if lowered == "not specified":
                return "Not specified"

        return value

    def update_by_user_id(self, user_id, profile_data: dict):
        """
        Update only fields explicitly supplied by the caller.

        Empty strings intentionally mean "remove this value", not
        "encrypt an empty string". Associated HMAC tokens are removed
        at the same time.
        """

        oid = self._object_id(user_id)
        existing = self.collection.find_one({"user_id": oid})

        if not existing:
            raise ValueError("Identity profile not found")

        update = {}
        unset = {}

        for field, db_field in self.ENCRYPTED_FIELDS.items():
            if field not in profile_data:
                continue

            raw_value = profile_data[field]
            value = "" if raw_value is None else str(raw_value).strip()

            # name_enc is required by the MongoDB validator.
            if field in self.REQUIRED_DB_FIELDS:
                if not value:
                    raise ValueError(
                        "Full name cannot be empty because it is required "
                        "to maintain a valid identity profile."
                    )
                update[db_field] = encrypt_text(value)
                continue

            if not value:
                unset[db_field] = ""
                token_field = self.TOKEN_FIELDS.get(field)
                if token_field:
                    unset[token_field] = ""
                continue

            if field == "phone":
                value = normalize_phone_number(value)
                if not value:
                    unset[db_field] = ""
                    unset[self.TOKEN_FIELDS[field]] = ""
                    continue

            update[db_field] = encrypt_text(value)

            token_field = self.TOKEN_FIELDS.get(field)
            if token_field:
                update[token_field] = tokenise(value)

        for field, db_field in self.PLAIN_FIELDS.items():
            if field not in profile_data:
                continue

            value = self._normalise_plain(field, profile_data[field])

            if value is None or value == "":
                unset[db_field] = ""
            else:
                update[db_field] = value

        update["updated_at"] = datetime.now(timezone.utc)

        operation = {}
        if update:
            operation["$set"] = update
        if unset:
            operation["$unset"] = unset

        if operation:
            self.collection.update_one({"user_id": oid}, operation)

        return self.get_by_user_id(oid)

    def delete_field(self, user_id, field_name: str):
        """
        Delete one supported profile value.

        The required name field cannot be removed individually because
        the patient_profiles MongoDB schema requires name_enc.
        """

        oid = self._object_id(user_id)

        if field_name not in self.ENCRYPTED_FIELDS and field_name not in self.PLAIN_FIELDS:
            raise ValueError(f"Unsupported profile field: {field_name}")

        if field_name in self.REQUIRED_DB_FIELDS:
            raise ValueError(
                "Full name cannot be deleted individually because "
                "name_enc is required by the profile schema."
            )

        existing = self.collection.find_one({"user_id": oid})
        if not existing:
            raise ValueError("Identity profile not found")

        unset = {}

        if field_name in self.ENCRYPTED_FIELDS:
            unset[self.ENCRYPTED_FIELDS[field_name]] = ""
            token_field = self.TOKEN_FIELDS.get(field_name)
            if token_field:
                unset[token_field] = ""

        elif field_name in self.PLAIN_FIELDS:
            unset[self.PLAIN_FIELDS[field_name]] = ""

        unset["updated_at"] = datetime.now(timezone.utc)

        # updated_at belongs in $set, not $unset.
        updated_at = unset.pop("updated_at")

        self.collection.update_one(
            {"user_id": oid},
            {
                "$unset": unset,
                "$set": {"updated_at": updated_at},
            },
        )

        return self.get_by_user_id(oid)

    def delete_profile(self, user_id) -> bool:
        """Delete the complete patient profile for the authenticated user."""

        oid = self._object_id(user_id)

        result = self.collection.delete_one({"user_id": oid})

        if result.deleted_count == 0:
            raise ValueError("Identity profile not found")

        return True

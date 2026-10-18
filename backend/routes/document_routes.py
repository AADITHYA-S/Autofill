from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.responses import JSONResponse

from backend.auth import get_authenticated_user_id
from backend.services.document_service import persist_extraction
from backend.dependencies import get_extraction_service
from backend.document_extraction.gemini_service import GeminiExtractionService
from backend.document_extraction.schemas import ExtractionResponse
from backend.settings import get_settings


router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class ConsentRequest(BaseModel):
    consent_given: bool
    extraction: dict


@router.post(
    "/extract",
    response_model=ExtractionResponse,
)
async def extract_document(
    file: UploadFile = File(...),
    service: GeminiExtractionService = Depends(
        get_extraction_service
    ),
    user_id=Depends(get_authenticated_user_id),
) -> ExtractionResponse:

    filename = file.filename or "document"
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: "
                f"{suffix or 'unknown'}. "
                "Allowed: pdf, jpg, jpeg, png"
            ),
        )

    temp_dir = get_settings().upload_dir
    temp_dir.mkdir(parents=True, exist_ok=True)

    temp_path = temp_dir / f"{uuid4().hex}{suffix}"

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="Uploaded file is empty",
            )

        temp_path.write_bytes(contents)

        result = service.extract_document(
            temp_path,
            ALLOWED_EXTENSIONS[suffix],
        )
        print("[EXTRACT] Gemini extraction completed")
        print("[EXTRACT] Result type:", type(result))
        print("[EXTRACT] Result:", result)

        response_data = result.model_dump(mode="json")

        print("[EXTRACT] Response data prepared:")
        print(response_data)

        return JSONResponse(
            content=response_data
        )

        # IMPORTANT:
        # Extraction is returned to the frontend only.
        # Nothing is persisted before explicit user consent.
        # return result

    except HTTPException:
        raise

    except Exception as exc:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def convert_extraction_for_persistence(
    extraction: dict,
) -> dict:
    """
    Convert the Gemini ExtractionResponse structure:

        {
            "status": "success",
            "document_type": "aadhaar",
            "overall_confidence": 0.92,
            "extracted_fields": {
                "full_name": {
                    "value": "...",
                    "confidence": 0.98
                }
            }
        }

    into the structure expected by persist_extraction():

        {
            "document_type": "aadhaar",
            "confidence_score": 0.92,
            "full_name": {
                "value": "..."
            }
        }

    This conversion happens ONLY after consent.
    """

    if not isinstance(extraction, dict):
        raise ValueError("Extraction must be an object.")

    document_type = extraction.get("document_type")

    if not document_type:
        raise ValueError("Missing document_type in extraction.")

    document_type = str(document_type).strip().lower()

    allowed_document_types = {
        "aadhaar",
        "pan_card",
        "passport",
        "driving_licence",
        "voter_id",
        "birth_certificate",
        "health_insurance_card",
        "form_scan",
        "other",
    }

    if document_type not in allowed_document_types:
        raise ValueError(
            f"Unsupported document_type: {document_type}"
        )

    overall_confidence = extraction.get(
        "overall_confidence",
        extraction.get("confidence_score", 0.0),
    )

    try:
        confidence_score = float(overall_confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "overall_confidence must be numeric."
        ) from exc

    extracted_fields = extraction.get(
        "extracted_fields",
        {},
    )

    if not isinstance(extracted_fields, dict):
        raise ValueError(
            "extracted_fields must be an object."
        )

    result = {
        "document_type": document_type,
        "confidence_score": confidence_score,
        "confidence_reason": extraction.get("confidence_reason", []),
    }

    for field_name, field_data in extracted_fields.items():

        if isinstance(field_data, dict):
            value = field_data.get("value")
        else:
            value = field_data

        result[field_name] = {
            "value": value,
        }

    return result


@router.post("/consent")
async def save_after_consent(
    payload: ConsentRequest,
    user_id=Depends(get_authenticated_user_id),
):
    """
    Persist extracted information ONLY after explicit consent.
    """

    if payload.consent_given is not True:
        raise HTTPException(
            status_code=400,
            detail="Explicit consent is required before saving.",
        )

    if not payload.extraction:
        raise HTTPException(
            status_code=400,
            detail="No extracted information was provided.",
        )

    try:
        persistence_data = convert_extraction_for_persistence(
            payload.extraction
        )

        print(
            "[CONSENT] Persisting approved extraction:",
            persistence_data,
        )

        persist_extraction(
            user_id,
            persistence_data,
        )

        return {
            "success": True,
            "message": (
                "Extracted information saved successfully."
            ),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Unable to save extracted information.",
        )

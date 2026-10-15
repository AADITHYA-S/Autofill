import base64
from pathlib import Path

from bson import ObjectId
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse

from backend.services.form_filling_service import FormFillingService
from backend.auth import get_authenticated_user_id

router = APIRouter(prefix="/api/forms", tags=["Forms"])
form_filling_service = FormFillingService()


@router.post("/fill")
async def fill_form(
    form: UploadFile = File(...),
    user_id: ObjectId = Depends(get_authenticated_user_id),
):
    result = await form_filling_service.fill(
        uploaded_file=form,
        user_id=user_id,
    )

    output_path = Path(result["output_path"])
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="The completed form could not be found.")

    output_suffix = output_path.suffix.lower()
    media_type = "application/pdf" if output_suffix == ".pdf" else "image/png"

    try:
        file_bytes = output_path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to read the completed form.") from exc

    return JSONResponse(
        content={
            "filename": f"filled_form{output_suffix}",
            "media_type": media_type,
            "file_base64": base64.b64encode(file_bytes).decode("ascii"),
            "review_items": result.get("review_items", []),
        }
    )

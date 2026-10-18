from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ExtractedField(BaseModel):
    value: Any | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class BoundingBox(BaseModel):
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    width: float = Field(..., gt=0.0, le=1.0)
    height: float = Field(..., gt=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_image_boundaries(self) -> "BoundingBox":
        if self.x + self.width > 1.0:
            raise ValueError(
                "Bounding box exceeds the image's right edge"
            )
        if self.y + self.height > 1.0:
            raise ValueError(
                "Bounding box exceeds the image's bottom edge"
            )
        return self


class ConfidenceReason(BaseModel):
    field: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    bounding_box: BoundingBox | None = None


class ExtractionResponse(BaseModel):
    status: Literal["success", "error"]
    document_type: str = Field(..., min_length=1)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_reason: list[ConfidenceReason] = Field(
        default_factory=list
    )
    extracted_fields: dict[str, ExtractedField] = Field(
        default_factory=dict
    )
    error: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
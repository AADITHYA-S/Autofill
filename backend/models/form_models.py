from pydantic import BaseModel
from typing import Optional

class FormField(BaseModel):
    label:str
    normalized_label:str
    value:str | None=None
    label_bbox:dict[str,float] |None=None
    value_bbox:dict[str,float] |None=None
    confidence:float
    field_type:Optional[str]=None
    source:str


class MatchField(BaseModel):
    form_field:FormField
    canonical_field:str| None=None
    matched_alias:str | None=None
    similarity_score:float
    type_compatible: bool | None = None
    type_warning: str | None = None
    # A review-only candidate; never used to autofill a rejected match.
    suggested_canonical_field: str | None = None

class AutofillField(BaseModel):
    form_field: FormField
    canonical_field: str
    value: str


class CellBox(BaseModel):
    row: int | float
    column: int | float
    bbox: dict[str,float]



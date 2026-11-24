from typing import Literal, Optional
from pydantic import BaseModel, Field

DocType = Literal["expense_claim", "leave_request", "purchase_request", "inquiry", "other"]


class Extraction(BaseModel):
    doc_type: DocType = "other"
    confidence: float = Field(0.0, ge=0, le=1)
    summary: str = ""
    requester: Optional[str] = None
    amount: Optional[int] = None          # KRW
    date_from: Optional[str] = None       # YYYY-MM-DD
    date_to: Optional[str] = None
    item: Optional[str] = None
    urgency: Literal["low", "normal", "high"] = "normal"


class SubmitIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    source: str = "api"

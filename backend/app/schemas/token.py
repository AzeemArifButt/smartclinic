from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TokenResponse(BaseModel):
    id: int
    token_number: int
    patient_phone: Optional[str]
    token_type: str
    issued_at: datetime
    doctor_id: int

    class Config:
        from_attributes = True


class WalkinIssueRequest(BaseModel):
    doctor_id: int

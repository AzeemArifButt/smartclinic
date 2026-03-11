from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TokenResponse(BaseModel):
    id: int
    token_number: int
    patient_phone: Optional[str]
    patient_name: Optional[str]
    patient_age: Optional[int]
    token_type: str
    issued_at: datetime
    doctor_id: int

    class Config:
        from_attributes = True


class WalkinIssueRequest(BaseModel):
    doctor_id: int
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None

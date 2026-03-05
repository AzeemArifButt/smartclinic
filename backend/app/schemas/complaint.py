from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ComplaintResponse(BaseModel):
    id: int
    patient_phone: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

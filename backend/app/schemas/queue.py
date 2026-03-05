from pydantic import BaseModel
from typing import List, Optional


class DoctorCreate(BaseModel):
    name: str
    specialty: Optional[str] = None


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    specialty: Optional[str] = None
    is_active: Optional[bool] = None


class DoctorResponse(BaseModel):
    id: int
    name: str
    specialty: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


class QueueStateResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    specialty: Optional[str]
    current_serving: int
    total_issued_today: int

    class Config:
        from_attributes = True


class QueueStatsResponse(BaseModel):
    doctors: List[QueueStateResponse]

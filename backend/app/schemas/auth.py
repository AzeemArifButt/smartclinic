from pydantic import BaseModel, EmailStr
from typing import Optional


class ClinicRegisterRequest(BaseModel):
    name: str
    city: str
    email: EmailStr
    password: str
    whatsapp_number: str  # e.g. +923001234567
    wa_phone_number_id: Optional[str] = None
    opening_time: str = "09:00"
    closing_time: str = "22:00"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    clinic_id: int
    clinic_name: str
    role: str


class ClinicResponse(BaseModel):
    id: int
    name: str
    city: str
    slug: str
    whatsapp_number: str
    wa_phone_number_id: Optional[str]
    staff_phones: Optional[str] = None
    opening_time: str
    closing_time: str
    plan: str

    class Config:
        from_attributes = True

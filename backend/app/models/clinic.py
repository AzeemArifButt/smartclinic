from sqlalchemy import Column, Integer, String, DateTime, Time
from sqlalchemy.sql import func
from app.core.database import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False, index=True)

    # WhatsApp: human-readable number e.g. +923001234567
    whatsapp_number = Column(String, nullable=False)
    # Meta Phone Number ID used for sending messages via API
    wa_phone_number_id = Column(String, nullable=True)
    # Comma-separated staff WhatsApp numbers (e.g. 923001234567,923009876543)
    staff_phones = Column(String, nullable=True)

    owner_email = Column(String, nullable=False)
    plan = Column(String, default="free")  # free, pro

    # Clinic hours in PKT (UTC+5), stored as HH:MM strings
    opening_time = Column(String, default="09:00")
    closing_time = Column(String, default="22:00")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

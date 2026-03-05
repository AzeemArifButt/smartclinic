from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    token_number = Column(Integer, nullable=False)
    # null for walk-in tokens
    patient_phone = Column(String, nullable=True, index=True)
    # whatsapp | walkin
    token_type = Column(String, default="whatsapp")
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    date = Column(Date, nullable=False, index=True)

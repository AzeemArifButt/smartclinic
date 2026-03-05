from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from app.core.database import Base


class ConversationState(Base):
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True, index=True)
    patient_phone = Column(String, nullable=False, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    # idle | selecting_doctor_text | awaiting_token_number | awaiting_complaint
    current_step = Column(String, default="idle")
    # stores doctor list, partial booking data, etc.
    temp_data = Column(JSON, default={})
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

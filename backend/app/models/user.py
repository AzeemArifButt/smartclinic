from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class ClinicUser(Base):
    __tablename__ = "clinic_users"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    # owner | receptionist
    role = Column(String, default="receptionist")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

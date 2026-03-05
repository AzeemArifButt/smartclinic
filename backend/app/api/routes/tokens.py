from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import ClinicUser
from app.models.doctor import Doctor
from app.schemas.token import TokenResponse, WalkinIssueRequest
from app.services import queue_service as qs

router = APIRouter()


@router.get("/tokens/today", response_model=List[TokenResponse])
def get_today_tokens(
    doctor_id: int,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.clinic_id == current_user.clinic_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return qs.get_today_tokens(db, current_user.clinic_id, doctor_id)


@router.post("/token/issue-walkin", response_model=TokenResponse)
def issue_walkin(
    payload: WalkinIssueRequest,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doctor = db.query(Doctor).filter(
        Doctor.id == payload.doctor_id,
        Doctor.clinic_id == current_user.clinic_id,
        Doctor.is_active == True,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found or inactive")

    token = qs.issue_token(
        db,
        current_user.clinic_id,
        payload.doctor_id,
        patient_phone=None,
        token_type="walkin",
    )
    return token

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import ClinicUser
from app.models.doctor import Doctor
from app.schemas.queue import (
    DoctorCreate,
    DoctorUpdate,
    DoctorResponse,
    QueueStateResponse,
    QueueStatsResponse,
)
from app.services import queue_service as qs

router = APIRouter()


@router.get("/queue/stats", response_model=QueueStatsResponse)
def get_queue_stats(
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doctors = qs.get_active_doctors(db, current_user.clinic_id)
    result = []
    for d in doctors:
        state = qs.get_or_create_queue_state(db, current_user.clinic_id, d.id)
        result.append(
            QueueStateResponse(
                doctor_id=d.id,
                doctor_name=d.name,
                specialty=d.specialty,
                current_serving=state.current_serving,
                total_issued_today=state.total_issued_today,
            )
        )
    return QueueStatsResponse(doctors=result)


@router.post("/queue/next")
def advance_queue(
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

    state = qs.advance_queue(db, current_user.clinic_id, doctor_id)
    return {"current_serving": state.current_serving}


@router.post("/queue/reset")
def reset_queue(
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

    qs.reset_queue(db, current_user.clinic_id, doctor_id)
    return {"message": "Queue reset successfully"}


# ── Doctors management ──

@router.get("/doctors", response_model=List[DoctorResponse])
def list_doctors(
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Doctor)
        .filter(Doctor.clinic_id == current_user.clinic_id)
        .order_by(Doctor.id)
        .all()
    )


@router.post("/doctors", response_model=DoctorResponse)
def create_doctor(
    payload: DoctorCreate,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    doctor = Doctor(
        clinic_id=current_user.clinic_id,
        name=payload.name,
        specialty=payload.specialty,
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    # Create queue state for the new doctor
    qs.get_or_create_queue_state(db, current_user.clinic_id, doctor.id)
    return doctor


@router.put("/doctors/{doctor_id}", response_model=DoctorResponse)
def update_doctor(
    doctor_id: int,
    payload: DoctorUpdate,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.clinic_id == current_user.clinic_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if payload.name is not None:
        doctor.name = payload.name
    if payload.specialty is not None:
        doctor.specialty = payload.specialty
    if payload.is_active is not None:
        doctor.is_active = payload.is_active

    db.commit()
    db.refresh(doctor)
    return doctor


@router.delete("/doctors/{doctor_id}")
def delete_doctor(
    doctor_id: int,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")

    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.clinic_id == current_user.clinic_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    db.delete(doctor)
    db.commit()
    return {"message": "Doctor deleted"}

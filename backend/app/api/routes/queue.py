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

    # Send near-turn WhatsApp notifications (free within 24h window)
    from app.models.clinic import Clinic
    from app.services import whatsapp_service as wa
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    if clinic and clinic.wa_phone_number_id:
        upcoming = qs.find_tokens_near_serving(
            db, current_user.clinic_id, doctor_id, state.current_serving
        )
        for t in upcoming:
            ahead = t.token_number - state.current_serving - 1
            msg = (
                f"🔔 *Your turn is coming soon!*\n"
                f"Token: *#{t.token_number}*\n"
                f"Now serving: #{state.current_serving}\n"
                f"{'You are next! Please come now.' if ahead == 0 else f'Only {ahead} patient(s) ahead of you.'}"
            )
            wa.send_text(clinic.wa_phone_number_id, t.patient_phone, msg)

    return {"current_serving": state.current_serving}


@router.post("/queue/prev")
def prev_queue(
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

    state = qs.get_or_create_queue_state(db, current_user.clinic_id, doctor_id)
    if state.current_serving <= 0:
        raise HTTPException(status_code=400, detail="Already at the beginning")
    state.current_serving -= 1
    db.commit()
    db.refresh(state)
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

    from app.models.queue import QueueState
    from app.models.token import Token
    db.query(QueueState).filter(QueueState.doctor_id == doctor_id).delete()
    db.query(Token).filter(Token.doctor_id == doctor_id).delete()
    db.delete(doctor)
    db.commit()
    return {"message": "Doctor deleted"}

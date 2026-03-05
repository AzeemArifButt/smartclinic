from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.doctor import Doctor
from app.models.queue import QueueState
from app.models.token import Token


def get_or_create_queue_state(db: Session, clinic_id: int, doctor_id: int) -> QueueState:
    qs = (
        db.query(QueueState)
        .filter(QueueState.clinic_id == clinic_id, QueueState.doctor_id == doctor_id)
        .first()
    )
    if not qs:
        qs = QueueState(
            clinic_id=clinic_id,
            doctor_id=doctor_id,
            current_serving=0,
            total_issued_today=0,
            last_reset_date=date.today(),
        )
        db.add(qs)
        db.commit()
        db.refresh(qs)
    return qs


def issue_token(
    db: Session,
    clinic_id: int,
    doctor_id: int,
    patient_phone: Optional[str],
    token_type: str = "whatsapp",
) -> Token:
    today = date.today()
    qs = get_or_create_queue_state(db, clinic_id, doctor_id)

    qs.total_issued_today += 1
    token_number = qs.total_issued_today
    db.commit()

    token = Token(
        clinic_id=clinic_id,
        doctor_id=doctor_id,
        token_number=token_number,
        patient_phone=patient_phone,
        token_type=token_type,
        date=today,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def advance_queue(db: Session, clinic_id: int, doctor_id: int) -> QueueState:
    qs = get_or_create_queue_state(db, clinic_id, doctor_id)
    qs.current_serving += 1
    db.commit()
    db.refresh(qs)
    return qs


def reset_queue(db: Session, clinic_id: int, doctor_id: int) -> QueueState:
    qs = get_or_create_queue_state(db, clinic_id, doctor_id)
    qs.current_serving = 0
    qs.total_issued_today = 0
    qs.last_reset_date = date.today()
    db.commit()
    db.refresh(qs)
    return qs


def get_today_tokens(db: Session, clinic_id: int, doctor_id: int) -> List[Token]:
    return (
        db.query(Token)
        .filter(
            Token.clinic_id == clinic_id,
            Token.doctor_id == doctor_id,
            Token.date == date.today(),
        )
        .order_by(Token.token_number)
        .all()
    )


def find_patient_token_today(
    db: Session, clinic_id: int, patient_phone: str
) -> Optional[Token]:
    return (
        db.query(Token)
        .filter(
            Token.clinic_id == clinic_id,
            Token.patient_phone == patient_phone,
            Token.date == date.today(),
        )
        .first()
    )


def find_token_by_number_today(
    db: Session, clinic_id: int, token_number: int
) -> Optional[Token]:
    return (
        db.query(Token)
        .filter(
            Token.clinic_id == clinic_id,
            Token.token_number == token_number,
            Token.date == date.today(),
        )
        .first()
    )


def get_active_doctors(db: Session, clinic_id: int) -> List[Doctor]:
    return (
        db.query(Doctor)
        .filter(Doctor.clinic_id == clinic_id, Doctor.is_active == True)
        .order_by(Doctor.id)
        .all()
    )


def midnight_reset_all(db: Session):
    """Called by scheduler at midnight PKT. Resets all clinics/doctors."""
    states = db.query(QueueState).all()
    today = date.today()
    for qs in states:
        qs.current_serving = 0
        qs.total_issued_today = 0
        qs.last_reset_date = today
    db.commit()

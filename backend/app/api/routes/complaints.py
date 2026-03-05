from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.complaint import Complaint
from app.models.user import ClinicUser
from app.schemas.complaint import ComplaintResponse

router = APIRouter()


@router.get("/complaints", response_model=List[ComplaintResponse])
def list_complaints(
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Complaint)
        .filter(Complaint.clinic_id == current_user.clinic_id)
        .order_by(Complaint.created_at.desc())
        .all()
    )


@router.get("/complaints/unread-count")
def unread_count(
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(Complaint)
        .filter(
            Complaint.clinic_id == current_user.clinic_id,
            Complaint.is_read == False,
        )
        .count()
    )
    return {"unread": count}


@router.post("/complaints/{complaint_id}/read")
def mark_read(
    complaint_id: int,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(
        Complaint.id == complaint_id,
        Complaint.clinic_id == current_user.clinic_id,
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    complaint.is_read = True
    db.commit()
    return {"message": "Marked as read"}

import re
import io
import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.models.clinic import Clinic
from app.models.user import ClinicUser
from app.schemas.auth import ClinicRegisterRequest, LoginRequest, TokenResponse, ClinicResponse
from app.api.deps import get_current_user

router = APIRouter()


def _generate_slug(name: str, city: str) -> str:
    raw = f"{name}-{city}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug


def _make_unique_slug(db: Session, base: str) -> str:
    slug = base
    counter = 1
    while db.query(Clinic).filter(Clinic.slug == slug).first():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


@router.post("/clinic/register", response_model=TokenResponse)
def register_clinic(payload: ClinicRegisterRequest, db: Session = Depends(get_db)):
    # Check email uniqueness
    existing = db.query(ClinicUser).filter(ClinicUser.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    base_slug = _generate_slug(payload.name, payload.city)
    slug = _make_unique_slug(db, base_slug)

    clinic = Clinic(
        name=payload.name,
        city=payload.city,
        slug=slug,
        whatsapp_number=payload.whatsapp_number,
        wa_phone_number_id=payload.wa_phone_number_id,
        owner_email=payload.email,
        opening_time=payload.opening_time,
        closing_time=payload.closing_time,
    )
    db.add(clinic)
    db.commit()
    db.refresh(clinic)

    user = ClinicUser(
        clinic_id=clinic.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "clinic_id": clinic.id, "role": user.role})
    return TokenResponse(
        access_token=token,
        clinic_id=clinic.id,
        clinic_name=clinic.name,
        role=user.role,
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(ClinicUser).filter(ClinicUser.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    clinic = db.query(Clinic).filter(Clinic.id == user.clinic_id).first()
    token = create_access_token({"sub": str(user.id), "clinic_id": user.clinic_id, "role": user.role})
    return TokenResponse(
        access_token=token,
        clinic_id=user.clinic_id,
        clinic_name=clinic.name if clinic else "",
        role=user.role,
    )


@router.get("/clinic/me", response_model=ClinicResponse)
def get_my_clinic(
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


@router.put("/clinic/me", response_model=ClinicResponse)
def update_clinic(
    payload: dict,
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    allowed = ["opening_time", "closing_time", "wa_phone_number_id", "whatsapp_number"]
    for key in allowed:
        if key in payload:
            setattr(clinic, key, payload[key])
    db.commit()
    db.refresh(clinic)
    return clinic


@router.get("/clinic/qr")
def get_qr_code(
    current_user: ClinicUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clinic = db.query(Clinic).filter(Clinic.id == current_user.clinic_id).first()
    url = f"{settings.FRONTEND_URL}/status/{clinic.slug}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")

"""
WhatsApp bot FSM.
Entry point: handle_message(db, clinic, message, phone_number_id)
"""
from datetime import datetime, timedelta
from typing import Optional
import pytz
from sqlalchemy.orm import Session

from app.models.clinic import Clinic
from app.models.complaint import Complaint
from app.models.conversation import ConversationState
from app.models.doctor import Doctor
from app.models.token import Token
from app.services import queue_service as qs
from app.services import whatsapp_service as wa

PKT = pytz.timezone("Asia/Karachi")
CONVO_TIMEOUT_MINUTES = 10


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _get_or_create_convo(db: Session, phone: str, clinic_id: int) -> ConversationState:
    convo = (
        db.query(ConversationState)
        .filter(
            ConversationState.patient_phone == phone,
            ConversationState.clinic_id == clinic_id,
        )
        .first()
    )
    if not convo:
        convo = ConversationState(
            patient_phone=phone,
            clinic_id=clinic_id,
            current_step="idle",
            temp_data={},
        )
        db.add(convo)
        db.commit()
        db.refresh(convo)
    return convo


def _reset_convo(db: Session, convo: ConversationState):
    convo.current_step = "idle"
    convo.temp_data = {}
    db.commit()


def _is_expired(convo: ConversationState) -> bool:
    if convo.current_step == "idle":
        return False
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    updated = convo.updated_at
    if updated.tzinfo is None:
        updated = pytz.utc.localize(updated)
    return (now_utc - updated) > timedelta(minutes=CONVO_TIMEOUT_MINUTES)


def _is_clinic_open(clinic: Clinic) -> bool:
    now_pkt = datetime.now(PKT)
    try:
        open_h, open_m = map(int, clinic.opening_time.split(":"))
        close_h, close_m = map(int, clinic.closing_time.split(":"))
    except Exception:
        return True  # fallback: always open

    current_minutes = now_pkt.hour * 60 + now_pkt.minute
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    return open_minutes <= current_minutes <= close_minutes


def _people_ahead(current_serving: int, token_number: int) -> int:
    ahead = token_number - current_serving - 1
    return max(0, ahead)


# ──────────────────────────────────────────────
# Main Menu
# ──────────────────────────────────────────────

def _send_main_menu(phone_number_id: str, to: str, clinic_name: str):
    wa.send_buttons(
        phone_number_id,
        to,
        body=f"Welcome to *{clinic_name}*! How can we help you?",
        buttons=[
            {"id": "book", "title": "Book Appointment"},
            {"id": "status", "title": "Check My Status"},
            {"id": "complaint", "title": "Add Complaint"},
        ],
        footer="Reply anytime to restart",
    )


# ──────────────────────────────────────────────
# Flow 1 — Book Appointment
# ──────────────────────────────────────────────

def _start_booking(
    db: Session,
    clinic: Clinic,
    phone: str,
    phone_number_id: str,
    convo: ConversationState,
):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, phone, "Sorry, no doctors are available right now.")
        return

    count = len(doctors)

    if count == 1:
        # Skip selection — book directly
        _complete_booking(db, clinic, phone, phone_number_id, doctors[0])
        return

    if count <= 3:
        buttons = [{"id": f"doc_{d.id}", "title": d.name[:20]} for d in doctors]
        wa.send_buttons(
            phone_number_id,
            phone,
            body="Please select a doctor:",
            buttons=buttons,
        )
        convo.current_step = "selecting_doctor"
        convo.temp_data = {"doctor_ids": [d.id for d in doctors]}
        db.commit()
        return

    if count <= 10:
        rows = [
            {
                "id": f"doc_{d.id}",
                "title": d.name[:24],
                "description": d.specialty or "",
            }
            for d in doctors
        ]
        wa.send_list(
            phone_number_id,
            phone,
            body="Please select a doctor from the list:",
            button_label="Select Doctor",
            sections=[{"title": "Available Doctors", "rows": rows}],
        )
        convo.current_step = "selecting_doctor"
        convo.temp_data = {"doctor_ids": [d.id for d in doctors]}
        db.commit()
        return

    # 10+ doctors — numbered text list
    lines = [f"{i+1}. Dr. {d.name}" + (f" ({d.specialty})" if d.specialty else "") for i, d in enumerate(doctors)]
    body = "Please reply with the *number* of your preferred doctor:\n\n" + "\n".join(lines)
    wa.send_text(phone_number_id, phone, body)
    convo.current_step = "selecting_doctor_text"
    convo.temp_data = {"doctor_ids": [d.id for d in doctors]}
    db.commit()


def _complete_booking(
    db: Session,
    clinic: Clinic,
    phone: str,
    phone_number_id: str,
    doctor: Doctor,
):
    # Check if already booked today
    existing = qs.find_patient_token_today(db, clinic.id, phone)
    if existing:
        existing_qs = qs.get_or_create_queue_state(db, clinic.id, existing.doctor_id)
        existing_doctor = db.query(Doctor).filter(Doctor.id == existing.doctor_id).first()
        wa.send_text(
            phone_number_id,
            phone,
            f"You already have token *#{existing.token_number}* with Dr. {existing_doctor.name}.\n"
            f"Now serving: #{existing_qs.current_serving}\n"
            f"People ahead: {_people_ahead(existing_qs.current_serving, existing.token_number)}",
        )
        return

    token = qs.issue_token(db, clinic.id, doctor.id, phone, token_type="whatsapp")
    queue_state = qs.get_or_create_queue_state(db, clinic.id, doctor.id)

    wa.send_text(
        phone_number_id,
        phone,
        f"✅ *Booked — Dr. {doctor.name}*\n"
        f"Your token: *#{token.token_number}*\n"
        f"Now serving: #{queue_state.current_serving}\n"
        f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
    )


# ──────────────────────────────────────────────
# Flow 2 — Check My Status
# ──────────────────────────────────────────────

def _check_status(
    db: Session,
    clinic: Clinic,
    phone: str,
    phone_number_id: str,
    convo: ConversationState,
):
    token = qs.find_patient_token_today(db, clinic.id, phone)
    if token:
        # Case A — already booked via WhatsApp
        doctor = db.query(Doctor).filter(Doctor.id == token.doctor_id).first()
        queue_state = qs.get_or_create_queue_state(db, clinic.id, token.doctor_id)
        wa.send_text(
            phone_number_id,
            phone,
            f"Your token: *#{token.token_number}*\n"
            f"Doctor: Dr. {doctor.name}\n"
            f"Now serving: #{queue_state.current_serving}\n"
            f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
        )
        return

    # Case C check: any token at all?
    # Prompt for walk-in token number (Case B path)
    wa.send_text(
        phone_number_id,
        phone,
        "We couldn't find a booking for your number.\n\n"
        "If you have a *walk-in slip*, please type your token number now.\n"
        "Or type *0* to see the general queue status.",
    )
    convo.current_step = "awaiting_token_number"
    db.commit()


def _handle_token_number_input(
    db: Session,
    clinic: Clinic,
    phone: str,
    phone_number_id: str,
    text: str,
    convo: ConversationState,
):
    text = text.strip()

    if text == "0":
        # Case C — show general overview
        _show_general_queue(db, clinic, phone, phone_number_id)
        _reset_convo(db, convo)
        return

    if not text.isdigit():
        wa.send_text(phone_number_id, phone, "Please enter a valid token number (digits only).")
        return

    token_num = int(text)
    token = qs.find_token_by_number_today(db, clinic.id, token_num)
    if not token:
        wa.send_text(
            phone_number_id,
            phone,
            "Token not found. Please check your slip.",
        )
        _reset_convo(db, convo)
        return

    # Link phone to this token (Case B)
    token.patient_phone = phone
    db.commit()

    doctor = db.query(Doctor).filter(Doctor.id == token.doctor_id).first()
    queue_state = qs.get_or_create_queue_state(db, clinic.id, token.doctor_id)
    wa.send_text(
        phone_number_id,
        phone,
        f"Your token: *#{token.token_number}*\n"
        f"Doctor: Dr. {doctor.name}\n"
        f"Now serving: #{queue_state.current_serving}\n"
        f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
    )
    _reset_convo(db, convo)


def _show_general_queue(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str
):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, phone, "No doctors are active right now.")
        return

    lines = []
    for d in doctors:
        queue_state = qs.get_or_create_queue_state(db, clinic.id, d.id)
        lines.append(
            f"Dr. {d.name} → Serving #{queue_state.current_serving}, "
            f"{queue_state.total_issued_today} issued"
        )

    body = "Current queue status:\n\n" + "\n".join(lines) + "\n\nWant to book? Reply *book*."
    wa.send_text(phone_number_id, phone, body)


# ──────────────────────────────────────────────
# Flow 3 — Complaint
# ──────────────────────────────────────────────

def _start_complaint(
    phone_number_id: str,
    phone: str,
    convo: ConversationState,
    db: Session,
):
    wa.send_text(
        phone_number_id,
        phone,
        "Please type your complaint and send it. We will pass it to the clinic.",
    )
    convo.current_step = "awaiting_complaint"
    db.commit()


def _save_complaint(
    db: Session,
    clinic: Clinic,
    phone: str,
    phone_number_id: str,
    message: str,
    convo: ConversationState,
):
    complaint = Complaint(
        clinic_id=clinic.id,
        patient_phone=phone,
        message=message,
    )
    db.add(complaint)
    db.commit()

    wa.send_text(
        phone_number_id,
        phone,
        "✅ Complaint received. The clinic has been notified. Thank you.",
    )
    _reset_convo(db, convo)


# ──────────────────────────────────────────────
# Main dispatcher
# ──────────────────────────────────────────────

def handle_message(
    db: Session,
    clinic: Clinic,
    from_phone: str,
    message_type: str,
    text_body: Optional[str],
    interactive_type: Optional[str],
    interactive_id: Optional[str],
    phone_number_id: str,
):
    if not _is_clinic_open(clinic):
        wa.send_text(
            phone_number_id,
            from_phone,
            f"Sorry, {clinic.name} is currently closed.\n"
            f"Opening hours: {clinic.opening_time} – {clinic.closing_time} (PKT).",
        )
        return

    convo = _get_or_create_convo(db, from_phone, clinic.id)

    # Expire stale state
    if _is_expired(convo):
        _reset_convo(db, convo)
        wa.send_text(
            phone_number_id,
            from_phone,
            "Your session expired. Starting over.",
        )

    step = convo.current_step

    # ── Interactive button/list replies ──
    if message_type == "interactive":
        btn_id = interactive_id or ""

        if btn_id == "book":
            _reset_convo(db, convo)
            _start_booking(db, clinic, from_phone, phone_number_id, convo)
            return

        if btn_id == "status":
            _reset_convo(db, convo)
            _check_status(db, clinic, from_phone, phone_number_id, convo)
            return

        if btn_id == "complaint":
            _reset_convo(db, convo)
            _start_complaint(phone_number_id, from_phone, convo, db)
            return

        if btn_id.startswith("doc_") and step == "selecting_doctor":
            doctor_id = int(btn_id.split("_")[1])
            allowed_ids = convo.temp_data.get("doctor_ids", [])
            if doctor_id not in allowed_ids:
                wa.send_text(phone_number_id, from_phone, "Invalid selection. Please try again.")
                return
            doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic.id).first()
            if not doctor or not doctor.is_active:
                wa.send_text(phone_number_id, from_phone, "That doctor is no longer available.")
                _reset_convo(db, convo)
                return
            _reset_convo(db, convo)
            _complete_booking(db, clinic, from_phone, phone_number_id, doctor)
            return

        # Unknown interactive — show main menu
        _reset_convo(db, convo)
        _send_main_menu(phone_number_id, from_phone, clinic.name)
        return

    # ── Text messages ──
    if message_type == "text" and text_body:
        body = text_body.strip()

        if step == "awaiting_complaint":
            _save_complaint(db, clinic, from_phone, phone_number_id, body, convo)
            return

        if step == "awaiting_token_number":
            _handle_token_number_input(db, clinic, from_phone, phone_number_id, body, convo)
            return

        if step == "selecting_doctor_text":
            if body.isdigit():
                idx = int(body) - 1
                doctor_ids = convo.temp_data.get("doctor_ids", [])
                if 0 <= idx < len(doctor_ids):
                    doctor = db.query(Doctor).filter(
                        Doctor.id == doctor_ids[idx],
                        Doctor.clinic_id == clinic.id,
                    ).first()
                    if doctor and doctor.is_active:
                        _reset_convo(db, convo)
                        _complete_booking(db, clinic, from_phone, phone_number_id, doctor)
                        return
                wa.send_text(
                    phone_number_id,
                    from_phone,
                    f"Invalid number. Please reply with a number between 1 and {len(doctor_ids)}.",
                )
            else:
                wa.send_text(
                    phone_number_id,
                    from_phone,
                    "Please reply with just the *number* of the doctor you want.",
                )
            return

        # Any other text → reset and show main menu
        _reset_convo(db, convo)
        _send_main_menu(phone_number_id, from_phone, clinic.name)
        return

    # Fallback
    _reset_convo(db, convo)
    _send_main_menu(phone_number_id, from_phone, clinic.name)

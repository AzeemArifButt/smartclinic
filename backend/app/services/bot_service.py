"""
WhatsApp bot FSM with:
- Language selection (English / Roman Urdu)
- Cancel appointment
- Near-turn notifications (sent from queue route)
- Staff walk-in token issuance
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
# Language helpers
# ──────────────────────────────────────────────

def _get_lang(convo: ConversationState) -> str:
    return (convo.temp_data or {}).get("lang", "en")


def _t(lang: str, en: str, ur: str) -> str:
    return ur if lang == "ur" else en


# ──────────────────────────────────────────────
# Core helpers
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
    # Preserve language across resets
    lang = (convo.temp_data or {}).get("lang")
    convo.current_step = "idle"
    convo.temp_data = {"lang": lang} if lang else {}
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
        return True
    current_minutes = now_pkt.hour * 60 + now_pkt.minute
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    return open_minutes <= current_minutes <= close_minutes


def _people_ahead(current_serving: int, token_number: int) -> int:
    return max(0, token_number - current_serving - 1)


def _is_staff(clinic: Clinic, phone: str) -> bool:
    if not clinic.staff_phones:
        return False
    staff_list = [p.strip() for p in clinic.staff_phones.split(",") if p.strip()]
    return phone in staff_list


# ──────────────────────────────────────────────
# Language Selection
# ──────────────────────────────────────────────

def _ask_language(phone_number_id: str, to: str):
    wa.send_buttons(
        phone_number_id,
        to,
        body="Welcome! Please select your language.\nخوش آمدید! زبان منتخب کریں۔",
        buttons=[
            {"id": "lang_en", "title": "English"},
            {"id": "lang_ur", "title": "Roman Urdu"},
        ],
    )


# ──────────────────────────────────────────────
# Main Menu
# ──────────────────────────────────────────────

def _send_main_menu(phone_number_id: str, to: str, clinic_name: str, lang: str = "en"):
    wa.send_buttons(
        phone_number_id,
        to,
        body=_t(
            lang,
            f"Welcome to *{clinic_name}*! How can we help you?",
            f"*{clinic_name}* mein khush aamdeed! Hum kaise madad karein?",
        ),
        buttons=[
            {"id": "book", "title": _t(lang, "Book Appointment", "Appointment Book")},
            {"id": "status", "title": _t(lang, "Check My Status", "Mera Status")},
            {"id": "complaint", "title": _t(lang, "Add Complaint", "Shikayat Darj")},
        ],
        footer=_t(lang, "Type 0 anytime to return here", "0 type karein wapas aanay ke liye"),
    )


# ──────────────────────────────────────────────
# Staff Mode
# ──────────────────────────────────────────────

def _send_staff_menu(phone_number_id: str, to: str):
    wa.send_buttons(
        phone_number_id,
        to,
        body="*Staff Menu* — Select an action:",
        buttons=[
            {"id": "staff_walkin", "title": "Issue Walk-in"},
            {"id": "staff_status", "title": "Queue Status"},
        ],
        footer="Type 0 to return here",
    )


def _send_staff_queue_status(db: Session, clinic: Clinic, to: str, phone_number_id: str):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, to, "No active doctors.")
        return
    lines = []
    for d in doctors:
        state = qs.get_or_create_queue_state(db, clinic.id, d.id)
        lines.append(
            f"Dr. {d.name}: Serving #{state.current_serving}, Total {state.total_issued_today}"
        )
    wa.send_text(phone_number_id, to, "📊 *Queue Status:*\n\n" + "\n".join(lines))


def _start_staff_walkin(
    db: Session, clinic: Clinic, from_phone: str, phone_number_id: str, convo: ConversationState
):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, from_phone, "No active doctors found.")
        return

    if len(doctors) == 1:
        token = qs.issue_token(db, clinic.id, doctors[0].id, None, token_type="walkin")
        wa.send_text(
            phone_number_id, from_phone,
            f"✅ Walk-in token issued!\nDoctor: Dr. {doctors[0].name}\nToken: *#{token.token_number}*",
        )
        _reset_convo(db, convo)
        return

    if len(doctors) <= 3:
        buttons = [{"id": f"sdoc_{d.id}", "title": d.name[:20]} for d in doctors]
        wa.send_buttons(phone_number_id, from_phone, body="Select doctor:", buttons=buttons)
    else:
        lines = [
            f"{i+1}. Dr. {d.name}" + (f" ({d.specialty})" if d.specialty else "")
            for i, d in enumerate(doctors)
        ]
        wa.send_text(phone_number_id, from_phone, "Reply with doctor number:\n\n" + "\n".join(lines))

    convo.current_step = "staff_selecting_doctor"
    convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
    db.commit()


def _handle_staff_message(
    db: Session, clinic: Clinic, from_phone: str, phone_number_id: str,
    message_type: str, text_body: Optional[str],
    interactive_type: Optional[str], interactive_id: Optional[str],
    convo: ConversationState,
):
    step = convo.current_step

    if message_type == "interactive":
        btn_id = interactive_id or ""

        if btn_id == "staff_walkin":
            _start_staff_walkin(db, clinic, from_phone, phone_number_id, convo)
            return

        if btn_id == "staff_status":
            _send_staff_queue_status(db, clinic, from_phone, phone_number_id)
            _reset_convo(db, convo)
            return

        if btn_id.startswith("sdoc_") and step == "staff_selecting_doctor":
            doctor_id = int(btn_id.split("_")[1])
            doctor = db.query(Doctor).filter(
                Doctor.id == doctor_id, Doctor.clinic_id == clinic.id
            ).first()
            if doctor and doctor.is_active:
                token = qs.issue_token(db, clinic.id, doctor.id, None, token_type="walkin")
                wa.send_text(
                    phone_number_id, from_phone,
                    f"✅ Walk-in token issued!\nDoctor: Dr. {doctor.name}\nToken: *#{token.token_number}*",
                )
            _reset_convo(db, convo)
            return

    if message_type == "text" and text_body:
        body = text_body.strip()

        if body.lower() in ("0", "menu", "staff"):
            _reset_convo(db, convo)
            _send_staff_menu(phone_number_id, from_phone)
            return

        if step == "staff_selecting_doctor" and body.isdigit():
            doctors = qs.get_active_doctors(db, clinic.id)
            idx = int(body) - 1
            if 0 <= idx < len(doctors):
                doctor = doctors[idx]
                token = qs.issue_token(db, clinic.id, doctor.id, None, token_type="walkin")
                wa.send_text(
                    phone_number_id, from_phone,
                    f"✅ Walk-in token issued!\nDoctor: Dr. {doctor.name}\nToken: *#{token.token_number}*",
                )
                _reset_convo(db, convo)
            else:
                wa.send_text(phone_number_id, from_phone, "Invalid selection. Try again.")
            return

    _reset_convo(db, convo)
    _send_staff_menu(phone_number_id, from_phone)


# ──────────────────────────────────────────────
# Flow 1 — Book Appointment
# ──────────────────────────────────────────────

def _start_booking(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    convo: ConversationState, lang: str,
):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(
            phone_number_id, phone,
            _t(lang, "Sorry, no doctors are available right now.", "Maafi, abhi koi doctor dastiyab nahi."),
        )
        return

    if len(doctors) == 1:
        _complete_booking(db, clinic, phone, phone_number_id, doctors[0], lang)
        return

    if len(doctors) <= 3:
        buttons = [{"id": f"doc_{d.id}", "title": d.name[:20]} for d in doctors]
        wa.send_buttons(
            phone_number_id, phone,
            body=_t(lang, "Please select a doctor:", "Doctor ka intikhaab karein:"),
            buttons=buttons,
        )
        convo.current_step = "selecting_doctor"
        convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
        db.commit()
        return

    if len(doctors) <= 10:
        rows = [
            {"id": f"doc_{d.id}", "title": d.name[:24], "description": d.specialty or ""}
            for d in doctors
        ]
        wa.send_list(
            phone_number_id, phone,
            body=_t(lang, "Please select a doctor from the list:", "Doctor ki list mein se chunein:"),
            button_label=_t(lang, "Select Doctor", "Doctor Chunein"),
            sections=[{"title": "Available Doctors", "rows": rows}],
        )
        convo.current_step = "selecting_doctor"
        convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
        db.commit()
        return

    lines = [
        f"{i+1}. Dr. {d.name}" + (f" ({d.specialty})" if d.specialty else "")
        for i, d in enumerate(doctors)
    ]
    wa.send_text(
        phone_number_id, phone,
        _t(lang, "Reply with the *number* of your preferred doctor:\n\n", "Doctor ka *number* type karein:\n\n")
        + "\n".join(lines),
    )
    convo.current_step = "selecting_doctor_text"
    convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
    db.commit()


def _complete_booking(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    doctor: Doctor, lang: str,
):
    existing = qs.find_patient_token_today(db, clinic.id, phone)
    if existing:
        existing_qs = qs.get_or_create_queue_state(db, clinic.id, existing.doctor_id)
        existing_doctor = db.query(Doctor).filter(Doctor.id == existing.doctor_id).first()
        wa.send_text(
            phone_number_id, phone,
            _t(
                lang,
                f"You already have token *#{existing.token_number}* with Dr. {existing_doctor.name}.\n"
                f"Now serving: #{existing_qs.current_serving}\n"
                f"People ahead: {_people_ahead(existing_qs.current_serving, existing.token_number)}",
                f"Aap ka pehlay se token *#{existing.token_number}* hai Dr. {existing_doctor.name} ke saath.\n"
                f"Abhi serving: #{existing_qs.current_serving}\n"
                f"Aap se pehle: {_people_ahead(existing_qs.current_serving, existing.token_number)}",
            ),
        )
        return

    token = qs.issue_token(db, clinic.id, doctor.id, phone, token_type="whatsapp")
    queue_state = qs.get_or_create_queue_state(db, clinic.id, doctor.id)
    wa.send_text(
        phone_number_id, phone,
        _t(
            lang,
            f"✅ *Booked — Dr. {doctor.name}*\n"
            f"Your token: *#{token.token_number}*\n"
            f"Now serving: #{queue_state.current_serving}\n"
            f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
            f"✅ *Appointment Book Ho Gayi — Dr. {doctor.name}*\n"
            f"Aap ka token: *#{token.token_number}*\n"
            f"Abhi serving: #{queue_state.current_serving}\n"
            f"Aap se pehle: {_people_ahead(queue_state.current_serving, token.token_number)}",
        ),
    )


# ──────────────────────────────────────────────
# Flow 2 — Check Status + Cancel
# ──────────────────────────────────────────────

def _check_status(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    convo: ConversationState, lang: str,
):
    token = qs.find_patient_token_today(db, clinic.id, phone)
    if token:
        doctor = db.query(Doctor).filter(Doctor.id == token.doctor_id).first()
        queue_state = qs.get_or_create_queue_state(db, clinic.id, token.doctor_id)
        wa.send_text(
            phone_number_id, phone,
            _t(
                lang,
                f"Your token: *#{token.token_number}*\n"
                f"Doctor: Dr. {doctor.name}\n"
                f"Now serving: #{queue_state.current_serving}\n"
                f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
                f"Aap ka token: *#{token.token_number}*\n"
                f"Doctor: Dr. {doctor.name}\n"
                f"Abhi serving: #{queue_state.current_serving}\n"
                f"Aap se pehle: {_people_ahead(queue_state.current_serving, token.token_number)}",
            ),
        )
        wa.send_buttons(
            phone_number_id, phone,
            body=_t(lang, "Options:", "Kya karna chahte hain?"),
            buttons=[
                {"id": "cancel_token", "title": _t(lang, "Cancel Token", "Token Cancel")},
                {"id": "book", "title": _t(lang, "Book Again", "Dobara Book")},
            ],
        )
        return

    wa.send_text(
        phone_number_id, phone,
        _t(
            lang,
            "We couldn't find a booking for your number.\n\n"
            "If you have a *walk-in slip*, type your token number.\n"
            "Or type *0* to see the general queue status.",
            "Aap ka koi booking nahi mila.\n\n"
            "Agar walk-in slip hai, token number type karein.\n"
            "Ya *0* type karein queue status dekhne ke liye.",
        ),
    )
    convo.current_step = "awaiting_token_number"
    db.commit()


# ──────────────────────────────────────────────
# Flow 3 — Complaint
# ──────────────────────────────────────────────

def _start_complaint(
    phone_number_id: str, phone: str, convo: ConversationState, db: Session, lang: str
):
    wa.send_text(
        phone_number_id, phone,
        _t(
            lang,
            "Please type your complaint. We will pass it to the clinic.",
            "Apni shikayat type karein. Hum clinic ko bhej denge.",
        ),
    )
    convo.current_step = "awaiting_complaint"
    db.commit()


def _save_complaint(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    message: str, convo: ConversationState, lang: str,
):
    complaint = Complaint(clinic_id=clinic.id, patient_phone=phone, message=message)
    db.add(complaint)
    db.commit()
    wa.send_text(
        phone_number_id, phone,
        _t(
            lang,
            "✅ Complaint received. The clinic has been notified. Thank you.",
            "✅ Shikayat mil gayi. Clinic ko bata diya gaya. Shukriya.",
        ),
    )
    _reset_convo(db, convo)


# ──────────────────────────────────────────────
# Token number input (walk-in lookup)
# ──────────────────────────────────────────────

def _handle_token_number_input(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    text: str, convo: ConversationState, lang: str,
):
    text = text.strip()

    if text == "0":
        _show_general_queue(db, clinic, phone, phone_number_id, lang)
        _reset_convo(db, convo)
        return

    if not text.isdigit():
        wa.send_text(
            phone_number_id, phone,
            _t(lang, "Please enter a valid token number (digits only).", "Sirf number type karein."),
        )
        return

    token = qs.find_token_by_number_today(db, clinic.id, int(text))
    if not token:
        wa.send_text(
            phone_number_id, phone,
            _t(lang, "Token not found. Please check your slip.", "Token nahi mila. Slip check karein."),
        )
        _reset_convo(db, convo)
        return

    token.patient_phone = phone
    db.commit()

    doctor = db.query(Doctor).filter(Doctor.id == token.doctor_id).first()
    queue_state = qs.get_or_create_queue_state(db, clinic.id, token.doctor_id)
    wa.send_text(
        phone_number_id, phone,
        _t(
            lang,
            f"Your token: *#{token.token_number}*\n"
            f"Doctor: Dr. {doctor.name}\n"
            f"Now serving: #{queue_state.current_serving}\n"
            f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
            f"Aap ka token: *#{token.token_number}*\n"
            f"Doctor: Dr. {doctor.name}\n"
            f"Abhi serving: #{queue_state.current_serving}\n"
            f"Aap se pehle: {_people_ahead(queue_state.current_serving, token.token_number)}",
        ),
    )
    _reset_convo(db, convo)


def _show_general_queue(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str, lang: str
):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(
            phone_number_id, phone,
            _t(lang, "No doctors are active right now.", "Abhi koi doctor active nahi."),
        )
        return
    lines = []
    for d in doctors:
        state = qs.get_or_create_queue_state(db, clinic.id, d.id)
        lines.append(f"Dr. {d.name} → Serving #{state.current_serving}, {state.total_issued_today} issued")
    body = (
        _t(lang, "Current queue status:\n\n", "Queue status:\n\n")
        + "\n".join(lines)
        + _t(lang, "\n\nWant to book? Reply *book*.", "\n\nBook karna hai? *book* type karein.")
    )
    wa.send_text(phone_number_id, phone, body)


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
    # Staff mode — bypass patient flow entirely
    if _is_staff(clinic, from_phone):
        convo = _get_or_create_convo(db, from_phone, clinic.id)
        _handle_staff_message(
            db, clinic, from_phone, phone_number_id,
            message_type, text_body, interactive_type, interactive_id, convo,
        )
        return

    if not _is_clinic_open(clinic):
        wa.send_text(
            phone_number_id, from_phone,
            f"Sorry, {clinic.name} is currently closed.\n"
            f"Opening hours: {clinic.opening_time} – {clinic.closing_time} (PKT).",
        )
        return

    convo = _get_or_create_convo(db, from_phone, clinic.id)

    if _is_expired(convo):
        _reset_convo(db, convo)
        wa.send_text(phone_number_id, from_phone, "Your session expired. Starting over.")

    lang = _get_lang(convo)
    step = convo.current_step

    # Language selection — first interaction
    if not (convo.temp_data or {}).get("lang"):
        if message_type == "interactive" and (interactive_id or "").startswith("lang_"):
            chosen = "ur" if interactive_id == "lang_ur" else "en"
            convo.temp_data = {"lang": chosen}
            convo.current_step = "idle"
            db.commit()
            _send_main_menu(phone_number_id, from_phone, clinic.name, chosen)
            return
        if step != "selecting_language":
            _ask_language(phone_number_id, from_phone)
            convo.current_step = "selecting_language"
            db.commit()
            return

    if step == "selecting_language":
        if message_type == "interactive" and (interactive_id or "").startswith("lang_"):
            chosen = "ur" if interactive_id == "lang_ur" else "en"
            convo.temp_data = {"lang": chosen}
            convo.current_step = "idle"
            db.commit()
            _send_main_menu(phone_number_id, from_phone, clinic.name, chosen)
            return
        if message_type == "text" and text_body:
            body = text_body.strip().lower()
            chosen = "ur" if ("urdu" in body or body == "ur" or "roman" in body) else "en"
            convo.temp_data = {"lang": chosen}
            convo.current_step = "idle"
            db.commit()
            _send_main_menu(phone_number_id, from_phone, clinic.name, chosen)
            return
        _ask_language(phone_number_id, from_phone)
        return

    # Interactive messages
    if message_type == "interactive":
        btn_id = interactive_id or ""

        if btn_id == "book":
            _reset_convo(db, convo)
            _start_booking(db, clinic, from_phone, phone_number_id, convo, lang)
            return

        if btn_id == "status":
            _reset_convo(db, convo)
            _check_status(db, clinic, from_phone, phone_number_id, convo, lang)
            return

        if btn_id == "complaint":
            _reset_convo(db, convo)
            _start_complaint(phone_number_id, from_phone, convo, db, lang)
            return

        if btn_id == "cancel_token":
            token = qs.find_patient_token_today(db, clinic.id, from_phone)
            if token:
                db.delete(token)
                db.commit()
                wa.send_text(
                    phone_number_id, from_phone,
                    _t(lang, "✅ Your token has been cancelled.", "✅ Aap ka token cancel ho gaya."),
                )
            else:
                wa.send_text(
                    phone_number_id, from_phone,
                    _t(lang, "No active token found to cancel.", "Cancel karne ke liye koi token nahi."),
                )
            _reset_convo(db, convo)
            return

        if btn_id.startswith("doc_") and step == "selecting_doctor":
            doctor_id = int(btn_id.split("_")[1])
            allowed_ids = (convo.temp_data or {}).get("doctor_ids", [])
            if doctor_id not in allowed_ids:
                wa.send_text(phone_number_id, from_phone, _t(lang, "Invalid selection.", "Ghalat chunaav."))
                return
            doctor = db.query(Doctor).filter(
                Doctor.id == doctor_id, Doctor.clinic_id == clinic.id
            ).first()
            if not doctor or not doctor.is_active:
                wa.send_text(
                    phone_number_id, from_phone,
                    _t(lang, "That doctor is no longer available.", "Woh doctor dastiyab nahi."),
                )
                _reset_convo(db, convo)
                return
            _reset_convo(db, convo)
            _complete_booking(db, clinic, from_phone, phone_number_id, doctor, lang)
            return

        _reset_convo(db, convo)
        _send_main_menu(phone_number_id, from_phone, clinic.name, lang)
        return

    # Text messages
    if message_type == "text" and text_body:
        body = text_body.strip()

        # Global shortcuts
        if body.lower() in ("0", "menu", "main menu", "hi", "hello", "start"):
            _reset_convo(db, convo)
            _send_main_menu(phone_number_id, from_phone, clinic.name, lang)
            return

        if step == "awaiting_complaint":
            _save_complaint(db, clinic, from_phone, phone_number_id, body, convo, lang)
            return

        if step == "awaiting_token_number":
            _handle_token_number_input(db, clinic, from_phone, phone_number_id, body, convo, lang)
            return

        if step == "selecting_doctor_text":
            if body.isdigit():
                idx = int(body) - 1
                doctor_ids = (convo.temp_data or {}).get("doctor_ids", [])
                if 0 <= idx < len(doctor_ids):
                    doctor = db.query(Doctor).filter(
                        Doctor.id == doctor_ids[idx],
                        Doctor.clinic_id == clinic.id,
                    ).first()
                    if doctor and doctor.is_active:
                        _reset_convo(db, convo)
                        _complete_booking(db, clinic, from_phone, phone_number_id, doctor, lang)
                        return
                wa.send_text(
                    phone_number_id, from_phone,
                    _t(
                        lang,
                        f"Invalid number. Reply with a number between 1 and {len(doctor_ids)}.",
                        f"Ghalat number. 1 aur {len(doctor_ids)} ke darmiyan type karein.",
                    ),
                )
            else:
                wa.send_text(
                    phone_number_id, from_phone,
                    _t(lang, "Please reply with just the *number* of the doctor.", "Sirf doctor ka *number* type karein."),
                )
            return

        _reset_convo(db, convo)
        _send_main_menu(phone_number_id, from_phone, clinic.name, lang)
        return

    # Fallback
    _reset_convo(db, convo)
    _send_main_menu(phone_number_id, from_phone, clinic.name, lang)

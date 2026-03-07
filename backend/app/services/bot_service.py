"""
WhatsApp bot FSM.
Features:
- Language selection (English / Roman Urdu)
- Booking: collects patient name + age for pharma analytics
- Status check / token cancel
- Complaint submission
- Walk-in token lookup
- Staff mode (issue walk-in, view queue)
- Every message has footer: ad text + "Reply 0 for Main Menu"
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


# ── Core helpers ──────────────────────────────────────────────────────────────

def _get_lang(convo: ConversationState) -> str:
    return (convo.temp_data or {}).get("lang", "en")


def _t(lang: str, en: str, ur: str) -> str:
    return ur if lang == "ur" else en


def _footer(clinic: Clinic, lang: str) -> str:
    """Footer shown on every message: pharma ad text + main menu hint."""
    menu_hint = _t(lang, "Reply 0 for Main Menu", "0 = Main Menu")
    if clinic.ad_text:
        return f"{clinic.ad_text} | {menu_hint}"
    return menu_hint


def _with_footer(text: str, clinic: Clinic, lang: str) -> str:
    """Append footer to plain text body (text messages have no separate footer field)."""
    return f"{text}\n\n{_footer(clinic, lang)}"


def _people_ahead(current_serving: int, token_number: int) -> int:
    return max(0, token_number - current_serving - 1)


def _is_clinic_open(clinic: Clinic) -> bool:
    now_pkt = datetime.now(PKT)
    try:
        open_h, open_m = map(int, clinic.opening_time.split(":"))
        close_h, close_m = map(int, clinic.closing_time.split(":"))
    except Exception:
        return True
    current_minutes = now_pkt.hour * 60 + now_pkt.minute
    return (open_h * 60 + open_m) <= current_minutes <= (close_h * 60 + close_m)


def _is_staff(clinic: Clinic, phone: str) -> bool:
    if not clinic.staff_phones:
        return False
    return phone in [p.strip() for p in clinic.staff_phones.split(",") if p.strip()]


def _is_expired(convo: ConversationState) -> bool:
    if convo.current_step == "idle":
        return False
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
    updated = convo.updated_at
    if updated.tzinfo is None:
        updated = pytz.utc.localize(updated)
    return (now_utc - updated) > timedelta(minutes=CONVO_TIMEOUT_MINUTES)


# ── Conversation helpers ──────────────────────────────────────────────────────

def _get_or_create_convo(db: Session, phone: str, clinic_id: int) -> ConversationState:
    convo = (
        db.query(ConversationState)
        .filter(ConversationState.patient_phone == phone, ConversationState.clinic_id == clinic_id)
        .first()
    )
    if not convo:
        convo = ConversationState(patient_phone=phone, clinic_id=clinic_id, current_step="idle", temp_data={})
        db.add(convo)
        db.commit()
        db.refresh(convo)
    return convo


def _reset_convo(db: Session, convo: ConversationState):
    lang = (convo.temp_data or {}).get("lang")
    convo.current_step = "idle"
    convo.temp_data = {"lang": lang} if lang else {}
    db.commit()


# ── Language ──────────────────────────────────────────────────────────────────

def _ask_language(phone_number_id: str, to: str):
    wa.send_buttons(
        phone_number_id, to,
        body="Welcome! Please select your language.\nخوش آمدید! زبان منتخب کریں۔",
        buttons=[{"id": "lang_en", "title": "English"}, {"id": "lang_ur", "title": "Roman Urdu"}],
    )


# ── Main Menu ─────────────────────────────────────────────────────────────────

def _send_main_menu(phone_number_id: str, to: str, clinic: Clinic, lang: str = "en"):
    wa.send_buttons(
        phone_number_id, to,
        body=_t(lang,
                f"Welcome to *{clinic.name}*! How can we help you?",
                f"*{clinic.name}* mein khush aamdeed! Hum kaise madad karein?"),
        buttons=[
            {"id": "book", "title": _t(lang, "Book Appointment", "Appointment Book")},
            {"id": "status", "title": _t(lang, "Check My Status", "Mera Status")},
            {"id": "complaint", "title": _t(lang, "Add Complaint", "Shikayat Darj")},
        ],
        footer=_footer(clinic, lang),
    )


# ── Staff Mode ────────────────────────────────────────────────────────────────

def _send_staff_menu(phone_number_id: str, to: str, clinic: Clinic):
    wa.send_buttons(
        phone_number_id, to,
        body="*Staff Menu* — Select an action:",
        buttons=[{"id": "staff_walkin", "title": "Issue Walk-in"}, {"id": "staff_status", "title": "Queue Status"}],
        footer=_footer(clinic, "en"),
    )


def _send_staff_queue_status(db: Session, clinic: Clinic, to: str, phone_number_id: str):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, to, _with_footer("No active doctors.", clinic, "en"))
        return
    lines = []
    for d in doctors:
        state = qs.get_or_create_queue_state(db, clinic.id, d.id)
        lines.append(f"Dr. {d.name}: Serving #{state.current_serving}, Total {state.total_issued_today}")
    wa.send_text(phone_number_id, to, _with_footer("📊 *Queue Status:*\n\n" + "\n".join(lines), clinic, "en"))


def _start_staff_walkin(db: Session, clinic: Clinic, from_phone: str, phone_number_id: str, convo: ConversationState):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, from_phone, _with_footer("No active doctors found.", clinic, "en"))
        return
    if len(doctors) == 1:
        token = qs.issue_token(db, clinic.id, doctors[0].id, None, token_type="walkin")
        wa.send_text(phone_number_id, from_phone,
            _with_footer(f"✅ Walk-in token issued!\nDoctor: Dr. {doctors[0].name}\nToken: *#{token.token_number}*", clinic, "en"))
        _reset_convo(db, convo)
        return
    if len(doctors) <= 3:
        wa.send_buttons(phone_number_id, from_phone, body="Select doctor:",
            buttons=[{"id": f"sdoc_{d.id}", "title": d.name[:20]} for d in doctors],
            footer=_footer(clinic, "en"))
    else:
        lines = [f"{i+1}. Dr. {d.name}" + (f" ({d.specialty})" if d.specialty else "") for i, d in enumerate(doctors)]
        wa.send_text(phone_number_id, from_phone, _with_footer("Reply with doctor number:\n\n" + "\n".join(lines), clinic, "en"))
    convo.current_step = "staff_selecting_doctor"
    convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
    db.commit()


def _handle_staff_message(
    db: Session, clinic: Clinic, from_phone: str, phone_number_id: str,
    message_type: str, text_body: Optional[str], interactive_id: Optional[str],
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
            doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic.id).first()
            if doctor and doctor.is_active:
                token = qs.issue_token(db, clinic.id, doctor.id, None, token_type="walkin")
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(f"✅ Walk-in token issued!\nDoctor: Dr. {doctor.name}\nToken: *#{token.token_number}*", clinic, "en"))
            _reset_convo(db, convo)
            return

    if message_type == "text" and text_body:
        body = text_body.strip()
        if body.lower() in ("0", "menu", "staff"):
            _reset_convo(db, convo)
            _send_staff_menu(phone_number_id, from_phone, clinic)
            return
        if step == "staff_selecting_doctor" and body.isdigit():
            doctors = qs.get_active_doctors(db, clinic.id)
            idx = int(body) - 1
            if 0 <= idx < len(doctors):
                token = qs.issue_token(db, clinic.id, doctors[idx].id, None, token_type="walkin")
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(f"✅ Walk-in token issued!\nDoctor: Dr. {doctors[idx].name}\nToken: *#{token.token_number}*", clinic, "en"))
                _reset_convo(db, convo)
            else:
                wa.send_text(phone_number_id, from_phone, _with_footer("Invalid selection. Try again.", clinic, "en"))
            return

    _reset_convo(db, convo)
    _send_staff_menu(phone_number_id, from_phone, clinic)


# ── Booking Flow ──────────────────────────────────────────────────────────────

def _start_name_collection(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    doctor: Doctor, convo: ConversationState, lang: str,
):
    """After doctor selected: check existing token, then ask for name."""
    existing = qs.find_patient_token_today(db, clinic.id, phone)
    if existing:
        existing_qs = qs.get_or_create_queue_state(db, clinic.id, existing.doctor_id)
        existing_doctor = db.query(Doctor).filter(Doctor.id == existing.doctor_id).first()
        wa.send_text(phone_number_id, phone,
            _with_footer(
                _t(lang,
                   f"You already have token *#{existing.token_number}* with Dr. {existing_doctor.name}.\n"
                   f"Now serving: #{existing_qs.current_serving}\n"
                   f"People ahead: {_people_ahead(existing_qs.current_serving, existing.token_number)}",
                   f"Aap ka pehlay se token *#{existing.token_number}* hai Dr. {existing_doctor.name} ke saath.\n"
                   f"Abhi serving: #{existing_qs.current_serving}\n"
                   f"Aap se pehle: {_people_ahead(existing_qs.current_serving, existing.token_number)}"),
                clinic, lang))
        _reset_convo(db, convo)
        return

    wa.send_text(phone_number_id, phone,
        _with_footer(
            _t(lang,
               f"Great! You selected Dr. {doctor.name}.\n\nPlease enter your *full name*:",
               f"Dr. {doctor.name} select ho gaye.\n\nApna *pura naam* likhein:"),
            clinic, lang))
    convo.current_step = "awaiting_name"
    convo.temp_data = {**(convo.temp_data or {}), "selected_doctor_id": doctor.id}
    db.commit()


def _complete_booking(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    doctor_id: int, name: str, age: int, lang: str,
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    token = qs.issue_token(db, clinic.id, doctor.id, phone, token_type="whatsapp",
                           patient_name=name, patient_age=age)
    queue_state = qs.get_or_create_queue_state(db, clinic.id, doctor.id)
    wa.send_text(phone_number_id, phone,
        _with_footer(
            _t(lang,
               f"✅ *Booked — Dr. {doctor.name}*\n"
               f"Name: {name} | Age: {age}\n"
               f"Your token: *#{token.token_number}*\n"
               f"Now serving: #{queue_state.current_serving}\n"
               f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
               f"✅ *Appointment Book Ho Gayi — Dr. {doctor.name}*\n"
               f"Naam: {name} | Umar: {age}\n"
               f"Aap ka token: *#{token.token_number}*\n"
               f"Abhi serving: #{queue_state.current_serving}\n"
               f"Aap se pehle: {_people_ahead(queue_state.current_serving, token.token_number)}"),
            clinic, lang))


def _start_booking(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    convo: ConversationState, lang: str,
):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, phone,
            _with_footer(_t(lang, "Sorry, no doctors are available right now.", "Maafi, abhi koi doctor dastiyab nahi."), clinic, lang))
        return

    if len(doctors) == 1:
        _start_name_collection(db, clinic, phone, phone_number_id, doctors[0], convo, lang)
        return

    if len(doctors) <= 3:
        wa.send_buttons(phone_number_id, phone,
            body=_t(lang, "Please select a doctor:", "Doctor ka intikhaab karein:"),
            buttons=[{"id": f"doc_{d.id}", "title": d.name[:20]} for d in doctors],
            footer=_footer(clinic, lang))
        convo.current_step = "selecting_doctor"
        convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
        db.commit()
        return

    if len(doctors) <= 10:
        rows = [{"id": f"doc_{d.id}", "title": d.name[:24], "description": d.specialty or ""} for d in doctors]
        wa.send_list(phone_number_id, phone,
            body=_t(lang, "Please select a doctor from the list:", "Doctor ki list mein se chunein:"),
            button_label=_t(lang, "Select Doctor", "Doctor Chunein"),
            sections=[{"title": "Available Doctors", "rows": rows}],
            footer=_footer(clinic, lang))
        convo.current_step = "selecting_doctor"
        convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
        db.commit()
        return

    lines = [f"{i+1}. Dr. {d.name}" + (f" ({d.specialty})" if d.specialty else "") for i, d in enumerate(doctors)]
    wa.send_text(phone_number_id, phone,
        _with_footer(
            _t(lang, "Reply with the *number* of your preferred doctor:\n\n", "Doctor ka *number* type karein:\n\n") + "\n".join(lines),
            clinic, lang))
    convo.current_step = "selecting_doctor_text"
    convo.temp_data = {**(convo.temp_data or {}), "doctor_ids": [d.id for d in doctors]}
    db.commit()


# ── Status Flow ───────────────────────────────────────────────────────────────

def _check_status(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    convo: ConversationState, lang: str,
):
    token = qs.find_patient_token_today(db, clinic.id, phone)
    if token:
        doctor = db.query(Doctor).filter(Doctor.id == token.doctor_id).first()
        queue_state = qs.get_or_create_queue_state(db, clinic.id, token.doctor_id)
        wa.send_text(phone_number_id, phone,
            _t(lang,
               f"Your token: *#{token.token_number}*\nDoctor: Dr. {doctor.name}\n"
               f"Now serving: #{queue_state.current_serving}\n"
               f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
               f"Aap ka token: *#{token.token_number}*\nDoctor: Dr. {doctor.name}\n"
               f"Abhi serving: #{queue_state.current_serving}\n"
               f"Aap se pehle: {_people_ahead(queue_state.current_serving, token.token_number)}"))
        wa.send_buttons(phone_number_id, phone,
            body=_t(lang, "Options:", "Kya karna chahte hain?"),
            buttons=[
                {"id": "cancel_token", "title": _t(lang, "Cancel Token", "Token Cancel")},
                {"id": "book", "title": _t(lang, "Book Again", "Dobara Book")},
            ],
            footer=_footer(clinic, lang))
        return

    wa.send_text(phone_number_id, phone,
        _with_footer(
            _t(lang,
               "We couldn't find a booking for your number.\n\n"
               "If you have a *walk-in slip*, type your token number.",
               "Aap ka koi booking nahi mila.\n\nAgar walk-in slip hai, token number type karein."),
            clinic, lang))
    convo.current_step = "awaiting_token_number"
    db.commit()


# ── Complaint Flow ────────────────────────────────────────────────────────────

def _start_complaint(phone_number_id: str, phone: str, convo: ConversationState, db: Session, clinic: Clinic, lang: str):
    wa.send_text(phone_number_id, phone,
        _with_footer(_t(lang, "Please type your complaint. We will pass it to the clinic.",
                            "Apni shikayat type karein. Hum clinic ko bhej denge."), clinic, lang))
    convo.current_step = "awaiting_complaint"
    db.commit()


def _save_complaint(db: Session, clinic: Clinic, phone: str, phone_number_id: str, message: str, convo: ConversationState, lang: str):
    complaint = Complaint(clinic_id=clinic.id, patient_phone=phone, message=message)
    db.add(complaint)
    db.commit()
    wa.send_text(phone_number_id, phone,
        _with_footer(_t(lang, "✅ Complaint received. The clinic has been notified. Thank you.",
                            "✅ Shikayat mil gayi. Clinic ko bata diya gaya. Shukriya."), clinic, lang))
    _reset_convo(db, convo)


# ── Walk-in Lookup ────────────────────────────────────────────────────────────

def _show_general_queue(db: Session, clinic: Clinic, phone: str, phone_number_id: str, lang: str):
    doctors = qs.get_active_doctors(db, clinic.id)
    if not doctors:
        wa.send_text(phone_number_id, phone, _with_footer(_t(lang, "No doctors are active right now.", "Abhi koi doctor active nahi."), clinic, lang))
        return
    lines = []
    for d in doctors:
        state = qs.get_or_create_queue_state(db, clinic.id, d.id)
        lines.append(f"Dr. {d.name} → Serving #{state.current_serving}, {state.total_issued_today} issued")
    wa.send_text(phone_number_id, phone,
        _with_footer(_t(lang, "Current queue status:\n\n", "Queue status:\n\n") + "\n".join(lines), clinic, lang))


def _handle_token_number_input(
    db: Session, clinic: Clinic, phone: str, phone_number_id: str,
    text: str, convo: ConversationState, lang: str,
):
    body = text.strip()
    if body == "0":
        _show_general_queue(db, clinic, phone, phone_number_id, lang)
        _reset_convo(db, convo)
        return
    if not body.isdigit():
        wa.send_text(phone_number_id, phone,
            _with_footer(_t(lang, "Please enter a valid token number (digits only).", "Sirf number type karein."), clinic, lang))
        return
    token = qs.find_token_by_number_today(db, clinic.id, int(body))
    if not token:
        wa.send_text(phone_number_id, phone,
            _with_footer(_t(lang, "Token not found. Please check your slip.", "Token nahi mila. Slip check karein."), clinic, lang))
        _reset_convo(db, convo)
        return
    token.patient_phone = phone
    db.commit()
    doctor = db.query(Doctor).filter(Doctor.id == token.doctor_id).first()
    queue_state = qs.get_or_create_queue_state(db, clinic.id, token.doctor_id)
    wa.send_text(phone_number_id, phone,
        _with_footer(
            _t(lang,
               f"Your token: *#{token.token_number}*\nDoctor: Dr. {doctor.name}\n"
               f"Now serving: #{queue_state.current_serving}\n"
               f"People ahead: {_people_ahead(queue_state.current_serving, token.token_number)}",
               f"Aap ka token: *#{token.token_number}*\nDoctor: Dr. {doctor.name}\n"
               f"Abhi serving: #{queue_state.current_serving}\n"
               f"Aap se pehle: {_people_ahead(queue_state.current_serving, token.token_number)}"),
            clinic, lang))
    _reset_convo(db, convo)


# ── Main Dispatcher ───────────────────────────────────────────────────────────

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
    # Staff mode
    if _is_staff(clinic, from_phone):
        convo = _get_or_create_convo(db, from_phone, clinic.id)
        _handle_staff_message(db, clinic, from_phone, phone_number_id, message_type, text_body, interactive_id, convo)
        return

    if not _is_clinic_open(clinic):
        wa.send_text(phone_number_id, from_phone,
            _with_footer(
                f"Sorry, {clinic.name} is currently closed.\n"
                f"Opening hours: {clinic.opening_time} – {clinic.closing_time} (PKT).",
                clinic, "en"))
        return

    convo = _get_or_create_convo(db, from_phone, clinic.id)

    if _is_expired(convo):
        _reset_convo(db, convo)
        wa.send_text(phone_number_id, from_phone, _with_footer("Your session expired. Starting over.", clinic, "en"))

    lang = _get_lang(convo)
    step = convo.current_step

    # Language not yet selected
    if not (convo.temp_data or {}).get("lang"):
        if message_type == "interactive" and (interactive_id or "").startswith("lang_"):
            chosen = "ur" if interactive_id == "lang_ur" else "en"
            convo.temp_data = {"lang": chosen}
            convo.current_step = "idle"
            db.commit()
            _send_main_menu(phone_number_id, from_phone, clinic, chosen)
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
            _send_main_menu(phone_number_id, from_phone, clinic, chosen)
            return
        if message_type == "text" and text_body:
            b = text_body.strip().lower()
            chosen = "ur" if ("urdu" in b or b == "ur" or "roman" in b) else "en"
            convo.temp_data = {"lang": chosen}
            convo.current_step = "idle"
            db.commit()
            _send_main_menu(phone_number_id, from_phone, clinic, chosen)
            return
        _ask_language(phone_number_id, from_phone)
        return

    # Global shortcut
    if message_type == "text" and text_body:
        if text_body.strip().lower() in ("0", "menu", "main menu", "hi", "hello", "start"):
            _reset_convo(db, convo)
            _send_main_menu(phone_number_id, from_phone, clinic, lang)
            return

    # ── Name collection ───────────────────────────────────────────────────────
    if step == "awaiting_name":
        if message_type == "text" and text_body and len(text_body.strip()) >= 2:
            name = text_body.strip()
            convo.temp_data = {**(convo.temp_data or {}), "patient_name": name}
            convo.current_step = "awaiting_age"
            db.commit()
            wa.send_text(phone_number_id, from_phone,
                _with_footer(_t(lang, f"Thanks, *{name}*! Now please enter your *age* (e.g. 35):",
                                      f"Shukriya, *{name}*! Ab apni *umar* likhein (masalan 35):"), clinic, lang))
            return
        wa.send_text(phone_number_id, from_phone,
            _with_footer(_t(lang, "Please enter your full name:", "Apna pura naam likhein:"), clinic, lang))
        return

    # ── Age collection ────────────────────────────────────────────────────────
    if step == "awaiting_age":
        if message_type == "text" and text_body and text_body.strip().isdigit():
            age = int(text_body.strip())
            if 1 <= age <= 120:
                name = (convo.temp_data or {}).get("patient_name", "")
                doctor_id = (convo.temp_data or {}).get("selected_doctor_id")
                _reset_convo(db, convo)
                _complete_booking(db, clinic, from_phone, phone_number_id, doctor_id, name, age, lang)
                return
        wa.send_text(phone_number_id, from_phone,
            _with_footer(_t(lang, "Please enter your age as a number (e.g. 35):", "Umar sirf number mein likhein (masalan 35):"), clinic, lang))
        return

    # ── Interactive messages ──────────────────────────────────────────────────
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
            _start_complaint(phone_number_id, from_phone, convo, db, clinic, lang)
            return
        if btn_id == "cancel_token":
            token = qs.find_patient_token_today(db, clinic.id, from_phone)
            if token:
                db.delete(token)
                db.commit()
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(_t(lang, "✅ Your token has been cancelled.", "✅ Aap ka token cancel ho gaya."), clinic, lang))
            else:
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(_t(lang, "No active token found to cancel.", "Cancel karne ke liye koi token nahi."), clinic, lang))
            _reset_convo(db, convo)
            return
        if btn_id.startswith("doc_") and step == "selecting_doctor":
            doctor_id = int(btn_id.split("_")[1])
            allowed_ids = (convo.temp_data or {}).get("doctor_ids", [])
            if doctor_id not in allowed_ids:
                wa.send_text(phone_number_id, from_phone, _with_footer(_t(lang, "Invalid selection.", "Ghalat chunaav."), clinic, lang))
                return
            doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.clinic_id == clinic.id).first()
            if not doctor or not doctor.is_active:
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(_t(lang, "That doctor is no longer available.", "Woh doctor dastiyab nahi."), clinic, lang))
                _reset_convo(db, convo)
                return
            _start_name_collection(db, clinic, from_phone, phone_number_id, doctor, convo, lang)
            return

        _reset_convo(db, convo)
        _send_main_menu(phone_number_id, from_phone, clinic, lang)
        return

    # ── Text messages ─────────────────────────────────────────────────────────
    if message_type == "text" and text_body:
        body = text_body.strip()

        if step == "awaiting_complaint":
            _save_complaint(db, clinic, from_phone, phone_number_id, body, convo, lang)
            return
        if step == "awaiting_token_number":
            _handle_token_number_input(db, clinic, from_phone, phone_number_id, body, convo, lang)
            return
        if step == "selecting_doctor_text":
            if body.isdigit():
                doctor_ids = (convo.temp_data or {}).get("doctor_ids", [])
                idx = int(body) - 1
                if 0 <= idx < len(doctor_ids):
                    doctor = db.query(Doctor).filter(Doctor.id == doctor_ids[idx], Doctor.clinic_id == clinic.id).first()
                    if doctor and doctor.is_active:
                        _start_name_collection(db, clinic, from_phone, phone_number_id, doctor, convo, lang)
                        return
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(_t(lang, f"Invalid number. Reply with a number between 1 and {len(doctor_ids)}.",
                                       f"Ghalat number. 1 aur {len(doctor_ids)} ke darmiyan type karein."), clinic, lang))
            else:
                wa.send_text(phone_number_id, from_phone,
                    _with_footer(_t(lang, "Please reply with just the *number* of the doctor.", "Sirf doctor ka *number* type karein."), clinic, lang))
            return

        _reset_convo(db, convo)
        _send_main_menu(phone_number_id, from_phone, clinic, lang)
        return

    # Fallback
    _reset_convo(db, convo)
    _send_main_menu(phone_number_id, from_phone, clinic, lang)

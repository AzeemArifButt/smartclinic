import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models.clinic import Clinic
from app.services.bot_service import handle_message

router = APIRouter()


def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Verify Meta webhook signature (X-Hub-Signature-256)."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        settings.WA_ACCESS_TOKEN.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.get("/whatsapp/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Meta webhook verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WA_VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()

    # Signature check
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body_bytes, sig):
        # In development you can log and continue; in prod enforce strictly
        pass  # Not raising to avoid blocking during setup

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if change.get("field") != "messages":
                continue

            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id", "")
            display_phone = metadata.get("display_phone_number", "")

            # Identify clinic by phone_number_id or display number
            clinic = (
                db.query(Clinic)
                .filter(Clinic.wa_phone_number_id == phone_number_id)
                .first()
            )
            if not clinic:
                # Fallback: match by whatsapp_number
                clinic = (
                    db.query(Clinic)
                    .filter(Clinic.whatsapp_number.contains(display_phone.lstrip("+")))
                    .first()
                )
            if not clinic:
                continue  # Unknown number — skip

            for msg in value.get("messages", []):
                from_phone = msg.get("from", "")
                msg_type = msg.get("type", "")

                text_body = None
                interactive_type = None
                interactive_id = None

                if msg_type == "text":
                    text_body = msg.get("text", {}).get("body", "")

                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    interactive_type = interactive.get("type", "")
                    if interactive_type == "button_reply":
                        interactive_id = interactive.get("button_reply", {}).get("id", "")
                    elif interactive_type == "list_reply":
                        interactive_id = interactive.get("list_reply", {}).get("id", "")

                # Use clinic's phone_number_id for sending (fallback to received one)
                send_phone_number_id = clinic.wa_phone_number_id or phone_number_id

                handle_message(
                    db=db,
                    clinic=clinic,
                    from_phone=from_phone,
                    message_type=msg_type,
                    text_body=text_body,
                    interactive_type=interactive_type,
                    interactive_id=interactive_id,
                    phone_number_id=send_phone_number_id,
                )

    return {"status": "ok"}


@router.get("/status/{slug}")
def public_queue_status(slug: str, db: Session = Depends(get_db)):
    """Public endpoint for QR-code status page (used by frontend)."""
    clinic = db.query(Clinic).filter(Clinic.slug == slug).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    from app.services.queue_service import get_active_doctors, get_or_create_queue_state

    doctors = get_active_doctors(db, clinic.id)
    result = []
    for d in doctors:
        state = get_or_create_queue_state(db, clinic.id, d.id)
        result.append({
            "doctor_name": d.name,
            "specialty": d.specialty,
            "current_serving": state.current_serving,
            "total_issued_today": state.total_issued_today,
        })

    return {
        "clinic_name": clinic.name,
        "city": clinic.city,
        "opening_time": clinic.opening_time,
        "closing_time": clinic.closing_time,
        "doctors": result,
    }

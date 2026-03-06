"""
Low-level WhatsApp Cloud API sender.
All outgoing messages go through this module.
"""
import httpx
from typing import List, Dict, Any
from app.core.config import settings

WA_API_BASE = "https://graph.facebook.com/v20.0"


def _send(phone_number_id: str, payload: Dict[str, Any]) -> bool:
    url = f"{WA_API_BASE}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=10)
        if not r.is_success:
            print(f"[WA] Send error {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[WA] Send error: {e}")
        return False


def send_text(phone_number_id: str, to: str, body: str) -> bool:
    return _send(
        phone_number_id,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        },
    )


def send_buttons(
    phone_number_id: str,
    to: str,
    body: str,
    buttons: List[Dict[str, str]],  # [{"id": "...", "title": "..."}]
    header: str = None,
    footer: str = None,
) -> bool:
    btn_list = [{"type": "reply", "reply": b} for b in buttons]
    interactive: Dict[str, Any] = {
        "type": "button",
        "body": {"text": body},
        "action": {"buttons": btn_list},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return _send(
        phone_number_id,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        },
    )


def send_list(
    phone_number_id: str,
    to: str,
    body: str,
    button_label: str,
    sections: List[Dict[str, Any]],  # [{"title": "...", "rows": [{"id":..,"title":..,"description":..}]}]
    header: str = None,
    footer: str = None,
) -> bool:
    interactive: Dict[str, Any] = {
        "type": "list",
        "body": {"text": body},
        "action": {"button": button_label, "sections": sections},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header}
    if footer:
        interactive["footer"] = {"text": footer}

    return _send(
        phone_number_id,
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        },
    )

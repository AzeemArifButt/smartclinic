from pydantic import BaseModel
from typing import Any, Dict, List, Optional


# Meta webhook payload structures

class WAProfile(BaseModel):
    name: Optional[str] = None


class WAContact(BaseModel):
    profile: Optional[WAProfile] = None
    wa_id: str


class WATextBody(BaseModel):
    body: str


class WAButtonReply(BaseModel):
    id: str
    title: str


class WAListReply(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class WAInteractive(BaseModel):
    type: str
    button_reply: Optional[WAButtonReply] = None
    list_reply: Optional[WAListReply] = None


class WAMessage(BaseModel):
    from_: str
    id: str
    timestamp: str
    type: str
    text: Optional[WATextBody] = None
    interactive: Optional[WAInteractive] = None

    class Config:
        populate_by_name = True
        fields = {"from_": "from"}


class WAMetadata(BaseModel):
    display_phone_number: str
    phone_number_id: str


class WAValue(BaseModel):
    messaging_product: str
    metadata: WAMetadata
    contacts: Optional[List[WAContact]] = None
    messages: Optional[List[WAMessage]] = None


class WAChange(BaseModel):
    value: WAValue
    field: str


class WAEntry(BaseModel):
    id: str
    changes: List[WAChange]


class WAWebhookPayload(BaseModel):
    object: str
    entry: List[WAEntry]

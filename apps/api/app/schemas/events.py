import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "client.transcript_segment",
    "client.transcript_final",
    "client.resume",
    "server.ack",
    "server.rule_alert",
    "server.guidance_update",
    "server.required_question_status",
    "system.ping",
    "system.pong",
    "system.resync",
]


class EventEnvelope(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    type: EventType
    ts_created: datetime
    schema_version: str = "1.0"
    payload: dict = Field(default_factory=dict)
    client_seq: int | None = None
    server_seq: int | None = None

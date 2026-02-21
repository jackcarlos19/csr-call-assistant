import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    tenant_id: str | None = None
    org_id: str | None = None
    location_id: str | None = None
    campaign_id: str | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    status: str
    tenant_id: str | None
    org_id: str | None
    location_id: str | None
    campaign_id: str | None
    ended_at: datetime | None = None
    summary: str | None = None
    disposition: str | None = None


class CallOutput(BaseModel):
    session_id: uuid.UUID
    summary: str
    disposition: str

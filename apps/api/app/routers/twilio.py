import uuid
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.call_session import CallSession
from app.schemas.sessions import SessionResponse
from app.services.twilio_service import TwilioService

router = APIRouter(prefix="/twilio", tags=["twilio"])
logger = structlog.get_logger()


@router.post("/voice/inbound")
async def inbound_call(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    form_data = {k: str(v) for k, v in form.items()}
    signature = request.headers.get("X-Twilio-Signature")

    twilio_service = TwilioService()
    if not twilio_service.validate_signature(str(request.url), form_data, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    session = CallSession()
    db.add(session)
    await db.commit()
    await db.refresh(session)

    query = urlencode({"source": "twilio", "session_id": str(session.id)})
    stream_url = f"{settings.twilio_stream_ws_base_url.rstrip('/')}/ws/session/{session.id}?{query}"
    twiml = twilio_service.build_stream_twiml(stream_url, str(session.id))

    logger.info(
        "twilio_inbound_call_connected",
        session_id=str(session.id),
        call_sid=form_data.get("CallSid"),
        from_number=form_data.get("From"),
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/status")
async def voice_status(request: Request):
    form = await request.form()
    payload = {k: str(v) for k, v in form.items()}
    logger.info(
        "twilio_voice_status",
        call_sid=payload.get("CallSid"),
        call_status=payload.get("CallStatus"),
    )
    return {"ok": True}


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_twilio_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    session = await db.get(CallSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

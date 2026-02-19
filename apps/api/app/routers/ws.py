"""
WebSocket router - thin endpoint that delegates all logic to WebSocketService.
"""

import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.db import async_session
from app.schemas.events import EventEnvelope
from app.services.websocket_service import WebSocketService, _fanout

router = APIRouter()
logger = structlog.get_logger()


@router.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: uuid.UUID):
    async with async_session() as db:
        service = WebSocketService(db)

        session = await service.accept_and_register(websocket, session_id)
        if session is None:
            return

        try:
            while True:
                structlog.contextvars.bind_contextvars(session_id=str(session_id))
                raw_message = await websocket.receive_text()

                try:
                    envelope = EventEnvelope.model_validate_json(raw_message)
                except ValidationError as exc:
                    logger.warning("ws_invalid_event_envelope", error=str(exc))
                    continue

                if envelope.type == "system.pong":
                    logger.debug("ws_pong_received", session_id=str(session_id))
                    continue

                if envelope.type == "client.resume":
                    await service.handle_resume(websocket, session_id, envelope.payload)
                    continue

                if envelope.type not in {
                    "client.transcript_segment",
                    "client.transcript_final",
                }:
                    logger.warning("ws_unsupported_event_type", event_type=envelope.type)
                    continue

                assigned_seq = await service.persist_event(session_id, envelope)

                outbound_payload = envelope.payload
                if envelope.type in {"client.transcript_segment", "client.transcript_final"}:
                    outbound_payload = service.pii_service.redact_dict(envelope.payload)

                outbound = envelope.model_copy(
                    update={
                        "session_id": session_id,
                        "server_seq": assigned_seq,
                        "payload": outbound_payload,
                    }
                )
                await _fanout(session_id, outbound.model_dump(mode="json"))

                if envelope.type == "client.transcript_segment":
                    text_content = str(envelope.payload.get("text", ""))
                    await service.evaluate_and_broadcast_rules(
                        session, session_id, text_content
                    )
                service.schedule_llm_guidance(session_id)

                ok = await service.send_ack(
                    websocket, envelope, session_id, assigned_seq
                )
                if not ok:
                    return

        except WebSocketDisconnect:
            logger.info("ws_disconnected", session_id=str(session_id))
        finally:
            await service.cleanup_connection(websocket, session_id)

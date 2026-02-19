import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import DefaultDict

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import async_session
from app.models.call_event import CallEvent
from app.models.call_session import CallSession
from app.schemas.events import EventEnvelope
from app.services.llm_client import LLMClient
from app.services.llm_service import LLMService
from app.services.pii_service import PIIService
from app.services.rule_service import RuleService

router = APIRouter()
logger = structlog.get_logger()
active_connections: DefaultDict[uuid.UUID, set[WebSocket]] = defaultdict(set)
last_seen: DefaultDict[uuid.UUID, dict[WebSocket, datetime]] = defaultdict(dict)
heartbeat_tasks: dict[uuid.UUID, asyncio.Task] = {}


def _is_duplicate_session_event_error(exc: IntegrityError) -> bool:
    return "uq_session_event" in str(exc.orig)


def _as_utc_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False
    except Exception:
        return False


async def _send_heartbeat(session_id: uuid.UUID) -> None:
    try:
        while True:
            await asyncio.sleep(30)
            if session_id not in active_connections or not active_connections[session_id]:
                return
            ping_event = EventEnvelope(
                session_id=session_id,
                type="system.ping",
                ts_created=datetime.now(timezone.utc),
                payload={},
            )
            stale_connections: list[WebSocket] = []
            for connection in list(active_connections[session_id]):
                ok = await _safe_send_json(connection, ping_event.model_dump(mode="json"))
                if not ok:
                    stale_connections.append(connection)
            for connection in stale_connections:
                active_connections[session_id].discard(connection)
                last_seen[session_id].pop(connection, None)
            if not active_connections[session_id]:
                active_connections.pop(session_id, None)
                last_seen.pop(session_id, None)
                return
    except asyncio.CancelledError:
        return


async def process_llm_guidance(session_id: uuid.UUID, llm_client: LLMClient) -> None:
    try:
        async with async_session() as task_db:
            llm_service = LLMService(task_db, llm_client)
            guidance_event = await llm_service.generate_guidance(session_id)
        if guidance_event is None:
            return

        stale_connections: list[WebSocket] = []
        for connection in list(active_connections.get(session_id, set())):
            ok = await _safe_send_json(connection, guidance_event.model_dump(mode="json"))
            if not ok:
                stale_connections.append(connection)
        for connection in stale_connections:
            active_connections[session_id].discard(connection)
            last_seen[session_id].pop(connection, None)
    except Exception as exc:
        logger.error("llm_guidance_generation_failed", session_id=str(session_id), error=str(exc))


@router.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: uuid.UUID):
    async with async_session() as db:
        session_result = await db.execute(
            select(CallSession).where(
                CallSession.id == session_id,
                CallSession.status == "active",
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            await websocket.close(code=1008, reason="Session not found or inactive")
            return

        await websocket.accept()
        active_connections[session_id].add(websocket)
        last_seen[session_id][websocket] = datetime.now(timezone.utc)
        if session_id not in heartbeat_tasks or heartbeat_tasks[session_id].done():
            heartbeat_tasks[session_id] = asyncio.create_task(_send_heartbeat(session_id))

        max_seq_result = await db.execute(
            select(func.max(CallEvent.server_seq)).where(CallEvent.session_id == session_id)
        )
        max_server_seq = max_seq_result.scalar_one_or_none()
        next_server_seq = (max_server_seq or 0) + 1
        rule_service = RuleService(db)
        llm_client = LLMClient()
        llm_service = LLMService(db, llm_client)
        pii_service = PIIService()

        try:
            while True:
                structlog.contextvars.bind_contextvars(session_id=str(session_id))
                raw_message = await websocket.receive_text()

                try:
                    envelope = EventEnvelope.model_validate_json(raw_message)
                except ValidationError as exc:
                    logger.warning("ws_invalid_event_envelope", session_id=str(session_id), error=str(exc))
                    continue

                if envelope.type == "system.pong":
                    last_seen[session_id][websocket] = datetime.now(timezone.utc)
                    logger.debug("ws_pong_received", session_id=str(session_id))
                    continue

                if envelope.type == "client.resume":
                    requested_seq = envelope.payload.get("last_server_seq")
                    if not isinstance(requested_seq, int):
                        logger.warning(
                            "ws_resume_invalid_payload",
                            session_id=str(session_id),
                            payload=envelope.payload,
                        )
                        continue
                    missed_events_result = await db.execute(
                        select(CallEvent)
                        .where(
                            CallEvent.session_id == session_id,
                            CallEvent.server_seq > requested_seq,
                        )
                        .order_by(CallEvent.server_seq.asc())
                    )
                    missed_events = missed_events_result.scalars().all()
                    for missed in missed_events:
                        replay_event = EventEnvelope(
                            event_id=missed.event_id,
                            session_id=session_id,
                            type=missed.type,
                            ts_created=_as_utc_datetime(missed.created_at),
                            payload=missed.payload or {},
                            server_seq=missed.server_seq,
                        )
                        ok = await _safe_send_json(websocket, replay_event.model_dump(mode="json"))
                        if not ok:
                            return
                    continue

                if envelope.type not in {"client.transcript_segment", "client.transcript_final"}:
                    logger.warning(
                        "ws_unsupported_event_type",
                        session_id=str(session_id),
                        event_type=envelope.type,
                    )
                    continue

                redacted_payload = envelope.payload
                if envelope.type in {"client.transcript_segment", "client.transcript_final"}:
                    redacted_payload = pii_service.redact_dict(envelope.payload)

                event = CallEvent(
                    session_id=session_id,
                    event_id=envelope.event_id,
                    server_seq=next_server_seq,
                    type=envelope.type,
                    payload=redacted_payload,
                )
                db.add(event)
                assigned_server_seq = next_server_seq
                try:
                    await db.commit()
                except IntegrityError as exc:
                    await db.rollback()
                    if _is_duplicate_session_event_error(exc):
                        existing_event_result = await db.execute(
                            select(CallEvent).where(
                                CallEvent.session_id == session_id,
                                CallEvent.event_id == envelope.event_id,
                            )
                        )
                        existing_event = existing_event_result.scalar_one_or_none()
                        if existing_event is None:
                            raise
                        assigned_server_seq = existing_event.server_seq
                    else:
                        raise
                else:
                    outbound_event = envelope.model_copy(
                        update={
                            "session_id": session_id,
                            "server_seq": assigned_server_seq,
                        }
                    )
                    disconnected_clients: list[WebSocket] = []
                    for connection in list(active_connections[session_id]):
                        ok = await _safe_send_json(connection, outbound_event.model_dump(mode="json"))
                        if not ok:
                            disconnected_clients.append(connection)
                    for connection in disconnected_clients:
                        active_connections[session_id].discard(connection)
                        last_seen[session_id].pop(connection, None)

                    if envelope.type == "client.transcript_final":
                        rule_server_seq = assigned_server_seq + 1
                        text = envelope.payload.get("text", "")
                        if not isinstance(text, str):
                            text = str(text)
                        rule_events = await rule_service.evaluate_segment(session, text)
                        logger.info(
                            "rules_triggered",
                            session_id=str(session_id),
                            count=len(rule_events),
                        )
                        for rule_event in rule_events:
                            rule_db_event = CallEvent(
                                session_id=session_id,
                                event_id=rule_event.event_id,
                                server_seq=rule_server_seq,
                                type=rule_event.type,
                                payload=rule_event.payload,
                            )
                            db.add(rule_db_event)
                            await db.commit()

                            outbound_rule_event = rule_event.model_copy(
                                update={
                                    "session_id": session_id,
                                    "server_seq": rule_server_seq,
                                }
                            )
                            stale_connections: list[WebSocket] = []
                            for connection in list(active_connections[session_id]):
                                ok = await _safe_send_json(
                                    connection, outbound_rule_event.model_dump(mode="json")
                                )
                                if not ok:
                                    stale_connections.append(connection)
                            for connection in stale_connections:
                                active_connections[session_id].discard(connection)
                                last_seen[session_id].pop(connection, None)

                            rule_server_seq += 1

                        asyncio.create_task(process_llm_guidance(session_id, llm_service.llm_client))

                max_seq_result = await db.execute(
                    select(func.max(CallEvent.server_seq)).where(CallEvent.session_id == session_id)
                )
                max_server_seq = max_seq_result.scalar_one_or_none()
                next_server_seq = (max_server_seq or 0) + 1

                ack = EventEnvelope(
                    event_id=envelope.event_id,
                    session_id=session_id,
                    type="server.ack",
                    ts_created=datetime.now(timezone.utc),
                    payload={"acknowledged": True},
                    client_seq=envelope.client_seq,
                    server_seq=assigned_server_seq,
                )
                ok = await _safe_send_json(websocket, ack.model_dump(mode="json"))
                if not ok:
                    return
        except WebSocketDisconnect:
            logger.info("ws_disconnected", session_id=str(session_id))
        finally:
            structlog.contextvars.unbind_contextvars("session_id")
            active_connections[session_id].discard(websocket)
            last_seen[session_id].pop(websocket, None)
            if not active_connections[session_id]:
                active_connections.pop(session_id, None)
                last_seen.pop(session_id, None)
                task = heartbeat_tasks.pop(session_id, None)
                if task is not None:
                    task.cancel()

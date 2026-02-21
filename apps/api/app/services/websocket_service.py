"""
WebSocket session service extracted from ws.py.
"""

import asyncio
import uuid
from collections import defaultdict
from datetime import UTC, datetime

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.models.call_event import CallEvent
from app.models.call_session import CallSession
from app.schemas.events import EventEnvelope
from app.services.llm_client import LLMClient
from app.services.llm_service import LLMService
from app.services.pii_service import PIIService
from app.services.rule_service import RuleService

logger = structlog.get_logger()

active_connections: defaultdict[uuid.UUID, set[WebSocket]] = defaultdict(set)
last_seen: defaultdict[uuid.UUID, dict[WebSocket, datetime]] = defaultdict(dict)
heartbeat_tasks: dict[uuid.UUID, asyncio.Task] = {}

_llm_pending_tasks: dict[uuid.UUID, asyncio.Task] = {}
LLM_DEBOUNCE_SECONDS = 1.5


class WebSocketService:
    """Connection lifecycle, persistence, rules, guidance, and fanout."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.rule_service = RuleService(db)
        self.llm_client = LLMClient()
        self.pii_service = PIIService()

    async def accept_and_register(
        self, websocket: WebSocket, session_id: uuid.UUID
    ) -> CallSession | None:
        session_result = await self.db.execute(
            select(CallSession).where(
                CallSession.id == session_id,
                CallSession.status == "active",
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            await websocket.close(code=1008, reason="Session not found or inactive")
            return None

        await websocket.accept()
        active_connections[session_id].add(websocket)
        last_seen[session_id][websocket] = datetime.now(UTC)

        if session_id not in heartbeat_tasks or heartbeat_tasks[session_id].done():
            heartbeat_tasks[session_id] = asyncio.create_task(_send_heartbeat(session_id))

        logger.info("ws_connected", session_id=str(session_id))
        return session

    async def cleanup_connection(
        self, websocket: WebSocket, session_id: uuid.UUID
    ) -> None:
        structlog.contextvars.unbind_contextvars("session_id")
        active_connections[session_id].discard(websocket)
        last_seen[session_id].pop(websocket, None)
        if not active_connections[session_id]:
            active_connections.pop(session_id, None)
            last_seen.pop(session_id, None)
            task = heartbeat_tasks.pop(session_id, None)
            if task is not None:
                task.cancel()
            pending = _llm_pending_tasks.pop(session_id, None)
            if pending is not None:
                pending.cancel()

    async def persist_event(
        self, session_id: uuid.UUID, envelope: EventEnvelope
    ) -> int:
        redacted_payload = envelope.payload
        if envelope.type in {"client.transcript_segment", "client.transcript_final"}:
            redacted_payload = self.pii_service.redact_dict(envelope.payload)

        try:
            assigned_seq = await _insert_with_advisory_lock(
                self.db, session_id, envelope.event_id, envelope.type, redacted_payload
            )
            return assigned_seq
        except IntegrityError as exc:
            await self.db.rollback()
            if "uq_session_event" in str(exc.orig):
                existing = await self.db.execute(
                    select(CallEvent).where(
                        CallEvent.session_id == session_id,
                        CallEvent.event_id == envelope.event_id,
                    )
                )
                row = existing.scalar_one_or_none()
                if row is not None:
                    return row.server_seq
            raise

    async def evaluate_and_broadcast_rules(
        self, session_id: uuid.UUID, tenant_id: str | None, text: str
    ) -> None:
        rule_events = await self.rule_service.evaluate_segment(session_id, tenant_id, text)
        logger.info("rules_triggered", session_id=str(session_id), count=len(rule_events))

        for rule_event in rule_events:
            seq = await _insert_with_advisory_lock(
                self.db,
                session_id,
                rule_event.event_id,
                rule_event.type,
                rule_event.payload,
            )
            outbound = rule_event.model_copy(
                update={"session_id": session_id, "server_seq": seq}
            )
            await _fanout(session_id, outbound.model_dump(mode="json"))

    def schedule_llm_guidance(self, session_id: uuid.UUID) -> None:
        existing = _llm_pending_tasks.get(session_id)
        if existing is not None and not existing.done():
            existing.cancel()

        _llm_pending_tasks[session_id] = asyncio.create_task(
            _debounced_llm_guidance(session_id, self.llm_client)
        )

    async def handle_resume(
        self, websocket: WebSocket, session_id: uuid.UUID, payload: dict
    ) -> None:
        requested_seq = payload.get("last_server_seq")
        if not isinstance(requested_seq, int):
            logger.warning(
                "ws_resume_invalid_payload",
                session_id=str(session_id),
                payload=payload,
            )
            return

        missed_result = await self.db.execute(
            select(CallEvent)
            .where(
                CallEvent.session_id == session_id,
                CallEvent.server_seq > requested_seq,
            )
            .order_by(CallEvent.server_seq.asc())
        )
        for missed in missed_result.scalars().all():
            replay_event = EventEnvelope(
                event_id=missed.event_id,
                session_id=session_id,
                type=missed.type,
                ts_created=_as_utc(missed.created_at),
                payload=missed.payload or {},
                server_seq=missed.server_seq,
            )
            ok = await _safe_send_json(websocket, replay_event.model_dump(mode="json"))
            if not ok:
                return

    async def send_ack(
        self,
        websocket: WebSocket,
        envelope: EventEnvelope,
        session_id: uuid.UUID,
        assigned_seq: int,
    ) -> bool:
        ack = EventEnvelope(
            event_id=envelope.event_id,
            session_id=session_id,
            type="server.ack",
            ts_created=datetime.now(UTC),
            payload={"acknowledged": True},
            client_seq=envelope.client_seq,
            server_seq=assigned_seq,
        )
        return await _safe_send_json(websocket, ack.model_dump(mode="json"))


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False
    except Exception:
        return False


async def _fanout(session_id: uuid.UUID, payload: dict) -> None:
    stale: list[WebSocket] = []
    for conn in list(active_connections.get(session_id, set())):
        ok = await _safe_send_json(conn, payload)
        if not ok:
            stale.append(conn)
    for conn in stale:
        active_connections[session_id].discard(conn)
        last_seen[session_id].pop(conn, None)


async def _send_heartbeat(session_id: uuid.UUID) -> None:
    try:
        while True:
            await asyncio.sleep(30)
            if session_id not in active_connections or not active_connections[session_id]:
                return
            ping = EventEnvelope(
                session_id=session_id,
                type="system.ping",
                ts_created=datetime.now(UTC),
                payload={},
            )
            await _fanout(session_id, ping.model_dump(mode="json"))
            if not active_connections.get(session_id):
                active_connections.pop(session_id, None)
                last_seen.pop(session_id, None)
                return
    except asyncio.CancelledError:
        return


def _lock_key_for_session(session_id: uuid.UUID) -> int:
    """Create a deterministic signed 64-bit key from UUID."""
    high = session_id.int >> 64
    low = session_id.int & ((1 << 64) - 1)
    return ((high ^ low) & ((1 << 63) - 1))


async def _insert_with_advisory_lock(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> int:
    lock_key = _lock_key_for_session(session_id)
    await db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})

    max_seq_result = await db.execute(
        select(func.max(CallEvent.server_seq)).where(CallEvent.session_id == session_id)
    )
    next_seq = (max_seq_result.scalar_one_or_none() or 0) + 1

    event = CallEvent(
        session_id=session_id,
        event_id=event_id,
        server_seq=next_seq,
        type=event_type,
        payload=payload,
    )
    db.add(event)
    await db.commit()
    return next_seq


async def _debounced_llm_guidance(session_id: uuid.UUID, llm_client: LLMClient) -> None:
    try:
        await asyncio.sleep(LLM_DEBOUNCE_SECONDS)
    except asyncio.CancelledError:
        return

    try:
        async with async_session() as task_db:
            llm_service = LLMService(task_db, llm_client)
            guidance_event = await llm_service.generate_guidance(session_id)
        if guidance_event is None:
            return
        await _fanout(session_id, guidance_event.model_dump(mode="json"))
    except Exception as exc:
        logger.error(
            "llm_guidance_generation_failed",
            session_id=str(session_id),
            error=str(exc),
        )
    finally:
        _llm_pending_tasks.pop(session_id, None)

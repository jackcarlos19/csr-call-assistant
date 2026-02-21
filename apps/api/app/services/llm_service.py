from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.call_event import CallEvent
from app.models.call_session import CallSession
from app.schemas.events import EventEnvelope
from app.schemas.guidance import CallSummaryResponse, GuidanceResponse
from app.schemas.sessions import CallOutput
from app.services.llm_client import LLMClient


class LLMService:
    def __init__(self, db: AsyncSession, llm_client: LLMClient) -> None:
        self.db = db
        self.llm_client = llm_client

    async def generate_guidance(self, session_id: UUID) -> EventEnvelope | None:
        transcript_stmt = (
            select(CallEvent)
            .where(
                CallEvent.session_id == session_id,
                CallEvent.type == "client.transcript_segment",
            )
            .order_by(CallEvent.server_seq.desc())
            .limit(20)
        )
        transcript_events = (await self.db.execute(transcript_stmt)).scalars().all()
        if not transcript_events:
            return None

        transcript_events = list(reversed(transcript_events))
        conversation_lines: list[str] = []
        for event in transcript_events:
            payload = event.payload or {}
            speaker = str(payload.get("speaker", "Customer"))
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            conversation_lines.append(f"{speaker.title()}: {text}")
        if not conversation_lines:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful CSR assistant. "
                    "Provide a short, direct suggested reply for the agent."
                ),
            },
            {"role": "user", "content": "\n".join(conversation_lines)},
        ]
        guidance = await self.llm_client.complete(messages, schema=GuidanceResponse)

        max_seq_result = await self.db.execute(
            select(func.max(CallEvent.server_seq)).where(CallEvent.session_id == session_id)
        )
        next_server_seq = (max_seq_result.scalar_one_or_none() or 0) + 1
        now = datetime.now(UTC)
        envelope = EventEnvelope(
            session_id=session_id,
            type="server.guidance_update",
            ts_created=now,
            payload=guidance.model_dump(mode="json"),
            server_seq=next_server_seq,
        )

        db_event = CallEvent(
            session_id=session_id,
            event_id=envelope.event_id,
            server_seq=next_server_seq,
            type=envelope.type,
            payload=envelope.payload,
            created_at=now,
        )
        self.db.add(db_event)
        await self.db.commit()
        return envelope

    async def generate_summary(self, session_id: UUID) -> CallOutput:
        session_result = await self.db.execute(
            select(CallSession).where(CallSession.id == session_id)
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            raise ValueError("Session not found")

        if session.summary and session.disposition:
            return CallOutput(
                session_id=session_id,
                summary=session.summary,
                disposition=session.disposition,
            )

        transcript_stmt = (
            select(CallEvent)
            .where(
                CallEvent.session_id == session_id,
                CallEvent.type.in_(["client.transcript_segment", "client.transcript_final"]),
            )
            .order_by(CallEvent.server_seq.asc())
        )
        transcript_events = (await self.db.execute(transcript_stmt)).scalars().all()
        conversation_lines: list[str] = []
        for event in transcript_events:
            payload = event.payload or {}
            speaker = str(payload.get("speaker", "Customer"))
            text = str(payload.get("text", "")).strip()
            if not text:
                continue
            conversation_lines.append(f"{speaker.title()}: {text}")

        if not conversation_lines:
            raise ValueError("No transcript data available for summary generation")

        messages = [
            {
                "role": "system",
                "content": (
                    "Summarize this call in 3 bullet points and provide a disposition. "
                    "Disposition must be one of: Booked, Lead, Spam."
                ),
            },
            {"role": "user", "content": "\n".join(conversation_lines)},
        ]
        summary_response = await self.llm_client.complete(messages, schema=CallSummaryResponse)

        session.status = "completed"
        session.ended_at = datetime.now(UTC)
        session.summary = summary_response.summary
        session.disposition = summary_response.disposition
        await self.db.commit()

        return CallOutput(
            session_id=session_id,
            summary=summary_response.summary,
            disposition=summary_response.disposition,
        )

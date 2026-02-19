import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import websockets

ACK_TIMEOUT_SECONDS = 8.0
MAX_ACK_RETRIES = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay transcript segments over WebSocket.")
    parser.add_argument("--session-id", required=True, help="Session UUID")
    parser.add_argument("--file", required=True, help="Path to transcript JSON file")
    parser.add_argument(
        "--deterministic",
        action="store_true",
        help="Use deterministic event IDs for repeatable replay",
    )
    parser.add_argument(
        "--simulate-resume",
        action="store_true",
        help="Disconnect at midpoint, reconnect, send client.resume, then continue",
    )
    return parser.parse_args()


def build_segment_event(
    session_id: uuid.UUID,
    client_seq: int,
    segment: dict,
    event_index: int | str,
    deterministic: bool,
    event_type: str = "client.transcript_segment",
) -> dict:
    if deterministic:
        event_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{session_id}-{event_index}")
    else:
        event_uuid = uuid.uuid4()
    return {
        "event_id": str(event_uuid),
        "session_id": str(session_id),
        "type": event_type,
        "ts_created": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "payload": {
            "speaker": segment.get("speaker"),
            "text": segment.get("text"),
            "timestamp_ms": segment.get("timestamp_ms"),
            "is_final": segment.get("is_final", True),
        },
        "client_seq": client_seq,
        "server_seq": None,
    }


async def wait_for_ack(ws, expected_event_id: str, timeout_seconds: float) -> dict:
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
        message = json.loads(raw)
        if message.get("type") != "server.ack":
            print(
                "Received event: "
                f"{message.get('type')} "
                f"(server_seq={message.get('server_seq')})"
            )
            continue
        if (
            message.get("type") == "server.ack"
            and message.get("event_id") == expected_event_id
        ):
            return message


async def send_resume(ws, session_id: uuid.UUID, last_server_seq: int, client_seq: int) -> None:
    resume_event = {
        "event_id": str(uuid.uuid4()),
        "session_id": str(session_id),
        "type": "client.resume",
        "ts_created": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",
        "payload": {"last_server_seq": last_server_seq},
        "client_seq": client_seq,
        "server_seq": None,
    }
    await ws.send(json.dumps(resume_event))
    print(f"Sent client.resume with last_server_seq={last_server_seq}")


async def drain_resume_replay(ws) -> None:
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.35)
        except TimeoutError:
            return
        message = json.loads(raw)
        if message.get("type") == "server.ack":
            continue
        print(
            "Received replay event "
            f"type={message.get('type')} server_seq={message.get('server_seq')}"
        )


async def wait_for_late_events(ws, cooldown_seconds: float = 5.0) -> None:
    print(f"Waiting {int(cooldown_seconds)}s for late-arriving events (LLM)...")
    end_time = asyncio.get_running_loop().time() + cooldown_seconds
    while True:
        remaining = end_time - asyncio.get_running_loop().time()
        if remaining <= 0:
            return
        timeout = min(0.5, remaining)
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        except asyncio.TimeoutError:
            continue
        message = json.loads(raw)
        print(
            "Received late event: "
            f"{message.get('type')} "
            f"(server_seq={message.get('server_seq')})"
        )


async def replay(
    session_id: uuid.UUID,
    transcript_file: Path,
    deterministic: bool,
    simulate_resume: bool,
) -> None:
    data = json.loads(transcript_file.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    full_transcript_text = " ".join(str(segment.get("text", "")) for segment in segments).strip()

    ws_url = f"ws://localhost:8000/ws/session/{session_id}"
    split_index = max(1, len(segments) // 2)
    client_seq = 1
    last_server_seq = 0

    def next_client_seq() -> int:
        nonlocal client_seq
        current = client_seq
        client_seq += 1
        return current

    async def connect_with_resume(current_last_server_seq: int):
        ws = await websockets.connect(ws_url)
        await send_resume(
            ws,
            session_id,
            current_last_server_seq,
            next_client_seq(),
        )
        await drain_resume_replay(ws)
        return ws

    async def send_event_with_ack(ws, event: dict) -> tuple[dict, int, object]:
        nonlocal last_server_seq
        for attempt in range(MAX_ACK_RETRIES + 1):
            try:
                await ws.send(json.dumps(event))
                ack = await wait_for_ack(ws, event["event_id"], ACK_TIMEOUT_SECONDS)
                ack_server_seq = ack.get("server_seq")
                if isinstance(ack_server_seq, int):
                    last_server_seq = ack_server_seq
                return ack, last_server_seq, ws
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, OSError) as exc:
                if attempt >= MAX_ACK_RETRIES:
                    raise RuntimeError(
                        f"Failed to receive ACK for event_id={event['event_id']} after retries"
                    ) from exc
                wait_seconds = min(2 ** attempt, 8)
                print(
                    f"ACK wait failed for event_id={event['event_id']} "
                    f"(attempt {attempt + 1}/{MAX_ACK_RETRIES + 1}). "
                    f"Reconnecting in {wait_seconds}s..."
                )
                await asyncio.sleep(wait_seconds)
                ws = await connect_with_resume(last_server_seq)
        raise RuntimeError("Unreachable ACK retry state")

    async def send_range(ws, start_index: int, end_index: int) -> tuple[int, int]:
        nonlocal client_seq
        nonlocal last_server_seq
        for index in range(start_index, end_index + 1):
            segment = segments[index - 1]
            event = build_segment_event(
                session_id,
                client_seq,
                segment,
                event_index=index,
                deterministic=deterministic,
            )
            print(f"Sent segment {index} with event_id={event['event_id']}")

            ack, _, ws = await send_event_with_ack(ws, event)
            print(
                "Received ACK "
                f"event_id={ack.get('event_id')} server_seq={ack.get('server_seq')}"
            )
            client_seq += 1
            await asyncio.sleep(0.5)
        return client_seq, last_server_seq

    if simulate_resume and segments:
        async with websockets.connect(ws_url) as ws:
            await send_range(ws, 1, split_index)
        print("Simulating disconnect...")
        await asyncio.sleep(2)
        async with websockets.connect(ws_url) as ws:
            await send_resume(ws, session_id, last_server_seq, next_client_seq())
            await drain_resume_replay(ws)
            if split_index < len(segments):
                await send_range(ws, split_index + 1, len(segments))

            final_event = build_segment_event(
                session_id,
                client_seq,
                {
                    "speaker": "system",
                    "text": full_transcript_text or "transcript_complete",
                    "timestamp_ms": None,
                    "is_final": True,
                },
                event_index="final",
                deterministic=deterministic,
                event_type="client.transcript_final",
            )
            print(f"Sent final event with event_id={final_event['event_id']}")

            ack, _, _ = await send_event_with_ack(ws, final_event)
            print(
                "Received ACK "
                f"event_id={ack.get('event_id')} server_seq={ack.get('server_seq')}"
            )
            await wait_for_late_events(ws)
        return

    async with websockets.connect(ws_url) as ws:
        if segments:
            await send_range(ws, 1, len(segments))

        final_event = build_segment_event(
            session_id,
            client_seq,
            {
                "speaker": "system",
                "text": full_transcript_text or "transcript_complete",
                "timestamp_ms": None,
                "is_final": True,
            },
            event_index="final",
            deterministic=deterministic,
            event_type="client.transcript_final",
        )
        print(f"Sent final event with event_id={final_event['event_id']}")

        ack, _, _ = await send_event_with_ack(ws, final_event)
        print(
            "Received ACK "
            f"event_id={ack.get('event_id')} server_seq={ack.get('server_seq')}"
        )
        await wait_for_late_events(ws)


def main() -> None:
    args = parse_args()
    session_id = uuid.UUID(args.session_id)
    transcript_file = Path(args.file)
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")
    asyncio.run(replay(session_id, transcript_file, args.deterministic, args.simulate_resume))


if __name__ == "__main__":
    main()

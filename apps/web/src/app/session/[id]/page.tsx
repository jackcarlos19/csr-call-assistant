"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import EndSessionControl from "@/components/EndSessionControl";
import GuidancePanel from "@/components/GuidancePanel";
import TranscriptPanel from "@/components/TranscriptPanel";
import { getSession } from "@/lib/api";
import { ServerEvent, SessionWebSocket } from "@/lib/ws";
import { useSessionStore } from "@/stores/sessionStore";

function formatTimestamp(payload: Record<string, unknown>, tsCreated: string): string {
  const timestampMs = payload.timestamp_ms;
  if (typeof timestampMs === "number") {
    return `${(timestampMs / 1000).toFixed(1)}s`;
  }
  return new Date(tsCreated).toLocaleTimeString();
}

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const sessionId = useMemo(() => {
    const value = params?.id;
    if (Array.isArray(value)) return value[0] ?? "";
    return value ?? "";
  }, [params]);

  const [error, setError] = useState<string | null>(null);
  const [autoEndSignal, setAutoEndSignal] = useState(0);
  const setSessionId = useSessionStore((state) => state.setSessionId);
  const setStatus = useSessionStore((state) => state.setStatus);
  const addSegment = useSessionStore((state) => state.addSegment);
  const setFullTranscript = useSessionStore((state) => state.setFullTranscript);
  const addAlert = useSessionStore((state) => state.addAlert);
  const updateQuestionStatus = useSessionStore((state) => state.updateQuestionStatus);
  const setSuggestedReply = useSessionStore((state) => state.setSuggestedReply);
  const reset = useSessionStore((state) => state.reset);
  const status = useSessionStore((state) => state.status);

  useEffect(() => {
    if (!sessionId) return;
    let wsClient: SessionWebSocket | null = null;
    let disposed = false;

    const handleEvent = (event: ServerEvent) => {
      if (event.type === "client.transcript_segment") {
        const speaker = String(event.payload.speaker ?? "unknown");
        const text = String(event.payload.text ?? "");
        addSegment({
          speaker,
          text,
          timestamp: formatTimestamp(event.payload, event.ts_created),
          isFinal: false,
        });
      }

      if (event.type === "client.transcript_final" || event.type === "server.transcript_final") {
        setStatus("processing");
        setFullTranscript(String(event.payload.text ?? ""));
        setAutoEndSignal((value) => value + 1);
      }

      if (event.type === "server.rule_alert") {
        addAlert({
          ruleId: String(event.payload.rule_id ?? "unknown_rule"),
          kind: String(event.payload.kind ?? "rule_alert"),
          severity: String(event.payload.severity ?? "info") as
            | "info"
            | "warning"
            | "high"
            | "critical",
          message: String(event.payload.message ?? "Rule alert triggered"),
          matchedPattern:
            event.payload.matched_pattern !== undefined
              ? String(event.payload.matched_pattern)
              : undefined,
        });
      }

      if (event.type === "server.required_question_status") {
        updateQuestionStatus(
          String(event.payload.rule_id ?? "unknown_question"),
          Boolean(event.payload.satisfied),
          event.payload.question ? String(event.payload.question) : undefined
        );
      }

      if (event.type === "server.guidance_update") {
        setSuggestedReply({
          text: String(event.payload.suggested_reply ?? ""),
          rationale: String(event.payload.rationale ?? ""),
          confidence: Number(event.payload.confidence ?? 0),
        });
      }
    };

    const init = async () => {
      try {
        setError(null);
        reset();
        setSessionId(sessionId);
        await getSession(sessionId);
        if (disposed) return;
        setStatus("active");
        wsClient = new SessionWebSocket(sessionId, handleEvent, (message) => {
          setError(message);
          setStatus("ended");
        });
        wsClient.connect();
      } catch (err) {
        if (disposed) return;
        setError(err instanceof Error ? err.message : "Failed to initialize session");
        setStatus("ended");
      }
    };

    init();

    return () => {
      disposed = true;
      wsClient?.disconnect();
    };
  }, [
    sessionId,
    addAlert,
    addSegment,
    reset,
    setFullTranscript,
    setSessionId,
    setStatus,
    setSuggestedReply,
    updateQuestionStatus,
  ]);

  return (
    <main className="min-h-screen bg-slate-950 px-6 py-8 text-slate-100">
      <div className="mx-auto flex max-w-7xl items-center justify-between rounded-lg border border-slate-800 bg-slate-900 px-4 py-3">
        <p className="text-sm text-slate-300">
          Session: <span className="font-mono text-slate-100">{sessionId || "..."}</span>
        </p>
        <p className="text-sm">
          Status:{" "}
          <span className={status === "active" ? "text-emerald-400" : "text-rose-400"}>
            ● {status}
          </span>
        </p>
      </div>

      {error ? (
        <div className="mx-auto mt-4 max-w-7xl rounded-md border border-red-900/50 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="mx-auto mt-4 grid h-[calc(100vh-11rem)] max-w-7xl grid-cols-1 gap-4 md:grid-cols-2">
        <TranscriptPanel />
        <div className="flex h-full flex-col gap-4">
          <EndSessionControl
            sessionId={sessionId}
            autoEndSignal={autoEndSignal}
            onCompleted={() => setStatus("completed")}
          />
          <div className="min-h-0 flex-1">
            <GuidancePanel />
          </div>
        </div>
      </div>
    </main>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { endSession, SessionSummaryOutput } from "@/lib/api";

interface EndSessionControlProps {
  sessionId: string;
  autoEndSignal: number;
  onCompleted?: () => void;
}

export default function EndSessionControl({
  sessionId,
  autoEndSignal,
  onCompleted,
}: EndSessionControlProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [output, setOutput] = useState<SessionSummaryOutput | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);

  const canEnd = useMemo(() => Boolean(sessionId) && !loading, [sessionId, loading]);

  const runEndSession = async () => {
    if (!canEnd) return;
    setLoading(true);
    setError(null);
    setCopySuccess(false);
    try {
      const result = await endSession(sessionId);
      setOutput(result);
      onCompleted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to end session");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (autoEndSignal > 0) {
      void runEndSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoEndSignal]);

  const copySummary = async () => {
    if (!output) return;
    await navigator.clipboard.writeText(
      `Disposition: ${output.disposition}\nSummary:\n${output.summary}`
    );
    setCopySuccess(true);
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">End Session</h2>
        <button
          onClick={() => void runEndSession()}
          disabled={!canEnd}
          className="rounded-md bg-rose-700 px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Generating Summary..." : "End Session"}
        </button>
      </div>

      {error ? (
        <p className="mt-3 rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      ) : null}

      {output ? (
        <div className="mt-3 rounded-md border border-slate-700 bg-slate-800/70 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Disposition</p>
          <p className="mt-1 text-sm font-semibold text-emerald-300">{output.disposition}</p>
          <p className="mt-3 whitespace-pre-wrap text-sm text-slate-100">{output.summary}</p>
          <div className="mt-3 flex items-center justify-between">
            <button
              onClick={() => void copySummary()}
              className="rounded-md border border-slate-600 px-2.5 py-1 text-xs text-slate-200 hover:bg-slate-700"
            >
              Copy to Clipboard
            </button>
            {copySuccess ? <span className="text-xs text-emerald-300">Copied</span> : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

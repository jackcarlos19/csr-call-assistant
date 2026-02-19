"use client";

import SuggestedReplyCard from "@/components/SuggestedReplyCard";
import { useSessionStore } from "@/stores/sessionStore";

function severityClass(severity: string): string {
  if (severity === "critical" || severity === "high") {
    return "border-red-600/60 bg-red-950/40";
  }
  if (severity === "warning") {
    return "border-yellow-600/60 bg-yellow-950/30";
  }
  return "border-slate-700 bg-slate-800/70";
}

export default function GuidancePanel() {
  const alerts = useSessionStore((state) => state.alerts);
  const requiredQuestions = useSessionStore((state) => state.requiredQuestions);
  const suggestedReply = useSessionStore((state) => state.suggestedReply);

  return (
    <div className="flex h-full flex-col gap-4">
      {suggestedReply ? <SuggestedReplyCard /> : null}
      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">Alerts</h2>
        <div className="mt-3 max-h-56 space-y-2 overflow-y-auto">
          {alerts.length === 0 ? (
            <p className="text-sm text-slate-400">No active rule alerts.</p>
          ) : (
            alerts.map((alert) => (
              <div
                key={`${alert.ruleId}-${alert.matchedPattern ?? "none"}-${alert.message}`}
                className={`rounded-md border p-3 ${severityClass(alert.severity)}`}
              >
                <p className="text-xs uppercase tracking-wide text-slate-300">
                  {alert.severity} • {alert.kind}
                </p>
                <p className="mt-1 text-sm text-slate-100">{alert.message}</p>
                <p className="mt-1 text-xs text-slate-400">Rule: {alert.ruleId}</p>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
          Required Questions
        </h2>
        <div className="mt-3 flex-1 space-y-2 overflow-y-auto">
          {requiredQuestions.length === 0 ? (
            <p className="text-sm text-slate-400">No required question updates yet.</p>
          ) : (
            requiredQuestions.map((question) => (
              <label
                key={question.ruleId}
                className="flex items-center gap-3 rounded-md border border-slate-700 bg-slate-800/70 px-3 py-2 text-sm"
              >
                <input
                  type="checkbox"
                  checked={question.satisfied}
                  readOnly
                  className="h-4 w-4 accent-emerald-500"
                />
                <span className={question.satisfied ? "text-emerald-300" : "text-slate-200"}>
                  {question.label}
                </span>
              </label>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

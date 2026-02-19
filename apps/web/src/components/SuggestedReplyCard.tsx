"use client";

import { useMemo } from "react";
import { useSessionStore } from "@/stores/sessionStore";

export default function SuggestedReplyCard() {
  const suggestedReply = useSessionStore((state) => state.suggestedReply);

  const animationKey = useMemo(() => {
    if (!suggestedReply) return "empty";
    return `${suggestedReply.text}-${suggestedReply.rationale}-${suggestedReply.confidence}`;
  }, [suggestedReply]);

  if (!suggestedReply) {
    return null;
  }

  const confidencePercent = `${Math.round(suggestedReply.confidence * 100)}% confidence`;

  return (
    <section
      key={animationKey}
      className="rounded-lg border border-cyan-700/50 bg-cyan-950/20 p-4"
      style={{ animation: "fadeIn 300ms ease-out" }}
    >
      <div className="flex items-center gap-2">
        <span className="rounded bg-cyan-700 px-2 py-0.5 text-xs font-semibold text-cyan-100">AI</span>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-cyan-200">Suggested Reply</h2>
      </div>
      <p className="mt-3 text-base leading-relaxed text-slate-100">{suggestedReply.text}</p>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
        <p className="text-slate-400">{suggestedReply.rationale}</p>
        <p className="whitespace-nowrap text-cyan-300">{confidencePercent}</p>
      </div>
      <style jsx>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
      `}</style>
    </section>
  );
}

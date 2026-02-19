"use client";

import { useEffect, useRef } from "react";
import { useSessionStore } from "@/stores/sessionStore";

export default function TranscriptPanel() {
  const transcript = useSessionStore((state) => state.transcript);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [transcript]);

  return (
    <div className="flex h-full flex-col rounded-lg border border-slate-800 bg-slate-900">
      <div className="border-b border-slate-800 px-4 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
          Transcript
        </h2>
      </div>
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-4">
        {transcript.length === 0 ? (
          <p className="text-sm text-slate-400">Waiting for transcript events...</p>
        ) : (
          transcript.map((segment, index) => {
            const isCsr = segment.speaker.toLowerCase() === "csr";
            return (
              <div key={`${segment.timestamp}-${index}`} className={isCsr ? "text-right" : "text-left"}>
                <div
                  className={
                    isCsr
                      ? "ml-auto inline-block max-w-[85%] rounded-lg bg-blue-600/20 px-3 py-2 text-slate-100"
                      : "mr-auto inline-block max-w-[85%] rounded-lg bg-slate-100/10 px-3 py-2 text-slate-100"
                  }
                >
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-300">
                    {segment.speaker}
                  </p>
                  <p className="mt-1 text-sm leading-relaxed">{segment.text}</p>
                  <p className="mt-2 text-[11px] text-slate-400">{segment.timestamp}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

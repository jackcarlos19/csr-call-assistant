import { create } from "zustand";

export interface TranscriptSegment {
  speaker: string;
  text: string;
  timestamp: string;
  isFinal: boolean;
}

export interface RuleAlert {
  ruleId: string;
  kind: string;
  severity: "info" | "warning" | "high" | "critical";
  message: string;
  matchedPattern?: string;
}

export interface RequiredQuestion {
  ruleId: string;
  satisfied: boolean;
  label: string;
}

export interface SuggestedReply {
  text: string;
  rationale: string;
  confidence: number;
}

interface SessionState {
  sessionId: string | null;
  status: "idle" | "active" | "processing" | "completed" | "ended";
  transcript: TranscriptSegment[];
  fullTranscript: string | null;
  alerts: RuleAlert[];
  requiredQuestions: RequiredQuestion[];
  suggestedReply: SuggestedReply | null;
  setSessionId: (id: string) => void;
  setStatus: (status: SessionState["status"]) => void;
  addSegment: (segment: TranscriptSegment) => void;
  setFullTranscript: (text: string) => void;
  addAlert: (alert: RuleAlert) => void;
  updateQuestionStatus: (ruleId: string, satisfied: boolean, label?: string) => void;
  setSuggestedReply: (reply: SuggestedReply) => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionId: null,
  status: "idle",
  transcript: [],
  fullTranscript: null,
  alerts: [],
  requiredQuestions: [],
  suggestedReply: null,
  setSessionId: (id) => set({ sessionId: id }),
  setStatus: (status) => set({ status }),
  addSegment: (segment) =>
    set((state) => ({ transcript: [...state.transcript, segment] })),
  setFullTranscript: (text) => set({ fullTranscript: text }),
  addAlert: (alert) =>
    set((state) => {
      const exists = state.alerts.some(
        (existing) =>
          existing.ruleId === alert.ruleId &&
          existing.message === alert.message &&
          existing.matchedPattern === alert.matchedPattern
      );
      if (exists) {
        return state;
      }
      return { alerts: [alert, ...state.alerts] };
    }),
  updateQuestionStatus: (ruleId, satisfied, label) =>
    set((state) => {
      const existing = state.requiredQuestions.find((question) => question.ruleId === ruleId);
      if (existing) {
        return {
          requiredQuestions: state.requiredQuestions.map((question) =>
            question.ruleId === ruleId ? { ...question, satisfied, label: label ?? question.label } : question
          ),
        };
      }
      return {
        requiredQuestions: [
          { ruleId, satisfied, label: label ?? ruleId.replaceAll("_", " ") },
          ...state.requiredQuestions,
        ],
      };
    }),
  setSuggestedReply: (reply) => set({ suggestedReply: reply }),
  reset: () =>
    set({
      sessionId: null,
      status: "idle",
      transcript: [],
      fullTranscript: null,
      alerts: [],
      requiredQuestions: [],
      suggestedReply: null,
    }),
}));

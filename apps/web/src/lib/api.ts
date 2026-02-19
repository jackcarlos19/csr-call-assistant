const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function createSession(params?: {
  tenant_id?: string;
  org_id?: string;
  location_id?: string;
  campaign_id?: string;
}) {
  const res = await fetch(`${API_URL}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params || {}),
  });
  if (!res.ok) throw new Error("Failed to create session");
  return res.json();
}

export async function getSession(id: string) {
  const res = await fetch(`${API_URL}/sessions/${id}`);
  if (!res.ok) throw new Error("Failed to get session");
  return res.json();
}

export interface SessionSummaryOutput {
  session_id: string;
  summary: string;
  disposition: string;
}

export async function endSession(id: string): Promise<SessionSummaryOutput> {
  const res = await fetch(`${API_URL}/sessions/${id}/end`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(errorText || "Failed to end session");
  }
  return res.json();
}

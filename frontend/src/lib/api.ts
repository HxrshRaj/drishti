export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const GATEWAY_BASE_URL = process.env.NEXT_PUBLIC_GATEWAY_BASE_URL ?? "http://localhost:8100";
export const INFERENCE_MODE = process.env.NEXT_PUBLIC_INFERENCE_MODE ?? "live"; // "live" | "replay"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface Site {
  site_id: string;
  name: string;
  weather: string;
  zones: { zone_id: string; zone_class: string; label: string }[];
  waypoints: { waypoint_id: string; site_id: string; x: number; y: number; altitude_m: number; zone_id: string | null }[];
}

export interface Drone {
  drone_id: string;
  site_id: string;
  status: string;
  battery_pct: number;
  position: [number, number];
}

export interface Mission {
  id: string;
  site_id: string;
  operator_goal: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  has_report: boolean;
}

export interface MissionReport {
  mission_id: string;
  report_text: string;
  report_summary: Record<string, unknown> | null;
}

export interface Finding {
  id: string;
  mission_id?: string;
  waypoint_id: string;
  finding_type: string;
  location_description?: string;
  severity: string;
  confidence: number;
  verifier_outcome: string;
  status: string;
  image_file: string;
  created_at?: string;
}

export interface AuditEvent {
  timestamp: string;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
}

export interface PendingApproval {
  id: string;
  mission_id: string;
  action_description: string;
  risk_level: string;
  proposing_agent: string;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface MissionRunResult {
  mission_id: string;
  status: string;
  findings?: Finding[];
  report?: { report_text?: string; computed_summary?: Record<string, unknown> } | null;
  interrupt?: { approval_id: string; waypoint_id: string; finding?: Record<string, unknown>; reason?: string };
}

export const api = {
  listSites: () => request<Site[]>("/sites"),
  getFleet: () => request<Drone[]>("/fleet"),
  listMissions: () => request<Mission[]>("/missions"),
  getMission: (id: string) => request<Mission>(`/missions/${id}`),
  startMission: (site_id: string, operator_goal: string, max_waypoints = 3) =>
    request<MissionRunResult>("/missions/start", {
      method: "POST",
      body: JSON.stringify({ site_id, operator_goal, max_waypoints }),
    }),
  decide: (missionId: string, decision: "approved" | "rejected", operator_id: string, rationale = "") =>
    request<MissionRunResult>(`/missions/${missionId}/decide`, {
      method: "POST",
      body: JSON.stringify({ decision, operator_id, rationale }),
    }),
  getAudit: (missionId: string) => request<AuditEvent[]>(`/missions/${missionId}/audit`),
  getMissionReport: (missionId: string) => request<MissionReport>(`/missions/${missionId}/report`),
  getMissionFindings: (missionId: string) => request<Finding[]>(`/missions/${missionId}/findings`),
  listAllFindings: () => request<Finding[]>("/findings"),
  getPendingApprovals: () => request<PendingApproval[]>("/missions/approvals/pending"),
  getMetricsManifest: () => request<Record<string, boolean>>("/metrics/manifest"),
  getRetrievalEval: () => request<Record<string, unknown>>("/metrics/retrieval"),
  getPerceptionEval: () => request<Record<string, unknown>>("/metrics/perception"),
  getParityReport: () => request<Record<string, unknown>>("/metrics/parity"),
  getBench: () => request<Record<string, unknown>>("/metrics/bench"),
};

export function imageUrl(filename: string): string {
  return `${GATEWAY_BASE_URL}/images/${filename}`;
}

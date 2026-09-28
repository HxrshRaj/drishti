"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, imageUrl, type AuditEvent, type Finding, type Mission, type MissionReport } from "@/lib/api";
import { SeverityBadge, VerifierBadge, Confidence } from "@/components/Badges";

const EVENT_ICONS: Record<string, string> = {
  mission_planned: "🗺️",
  goto: "🛰️",
  goto_failed: "⚠️",
  capture: "📸",
  capture_failed: "⚠️",
  rth: "🔁",
  approval_requested: "⏸️",
  approval_decided: "✅",
  action_blocked: "⛔",
  mission_completed: "🏁",
};

export default function MissionDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [mission, setMission] = useState<Mission | null>(null);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [report, setReport] = useState<MissionReport | null>(null);
  const [operatorId, setOperatorId] = useState("operator-1");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    api.getMission(id).then((m) => {
      setMission(m);
      if (m.has_report) api.getMissionReport(id).then(setReport).catch(() => {});
    }).catch(() => {});
    api.getAudit(id).then(setAudit).catch(() => {});
    api.getMissionFindings(id).then(setFindings).catch(() => {});
  }, [id]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [refresh]);

  const pendingApprovalEvent = audit?.find((e) => e.event_type === "approval_requested");
  const lastDecision = audit?.find((e) => e.event_type === "approval_decided");
  const showApprovalPanel = pendingApprovalEvent && (!lastDecision || new Date(lastDecision.timestamp) < new Date(pendingApprovalEvent.timestamp));

  async function decide(decision: "approved" | "rejected") {
    setBusy(true);
    try {
      await api.decide(id, decision, operatorId);
      refresh();
    } finally {
      setBusy(false);
    }
  }

  if (!mission) return <p className="text-sm text-neutral-500">Loading mission…</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/" className="text-xs text-sky-400 hover:underline">
          ← Missions
        </Link>
        <h1 className="text-xl font-semibold mt-1">
          {mission.site_id} <span className="text-neutral-500 font-normal">— {mission.operator_goal}</span>
        </h1>
        <p className="text-sm text-neutral-400 mt-1">
          status: <span className="font-medium">{mission.status}</span> · started {new Date(mission.started_at).toLocaleString()}
        </p>
      </div>

      {showApprovalPanel && (
        <div className="rounded-lg border border-amber-700/50 bg-amber-950/30 p-4">
          <h3 className="font-medium text-amber-300 mb-2">Awaiting operator approval</h3>
          <pre className="text-xs text-amber-100/80 whitespace-pre-wrap overflow-x-auto">
            {JSON.stringify(pendingApprovalEvent?.payload, null, 2)}
          </pre>
          <div className="mt-3 flex items-center gap-2">
            <input
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm w-40"
              placeholder="operator id"
            />
            <button
              onClick={() => decide("approved")}
              disabled={busy}
              className="rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-3 py-1.5 text-sm text-white"
            >
              Approve
            </button>
            <button
              onClick={() => decide("rejected")}
              disabled={busy}
              className="rounded bg-red-700 hover:bg-red-600 disabled:opacity-50 px-3 py-1.5 text-sm text-white"
            >
              Reject
            </button>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Agent timeline</h2>
          <ol className="space-y-2">
            {audit === null ? (
              <p className="text-sm text-neutral-500">Loading…</p>
            ) : audit.length === 0 ? (
              <p className="text-sm text-neutral-500">No events yet.</p>
            ) : (
              [...audit].reverse().map((e, i) => (
                <li key={i} className="rounded border border-neutral-800 bg-neutral-900/40 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between">
                    <span>
                      <span className="mr-1">{EVENT_ICONS[e.event_type] ?? "•"}</span>
                      <span className="font-medium">{e.event_type}</span>
                      <span className="text-neutral-500"> · {e.actor}</span>
                    </span>
                    <span className="text-neutral-600">{new Date(e.timestamp).toLocaleTimeString()}</span>
                  </div>
                  {Object.keys(e.payload ?? {}).length > 0 && (
                    <pre className="mt-1 text-neutral-500 whitespace-pre-wrap break-all">
                      {JSON.stringify(e.payload)}
                    </pre>
                  )}
                </li>
              ))
            )}
          </ol>
        </section>

        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Findings</h2>
          <div className="space-y-3">
            {findings === null ? (
              <p className="text-sm text-neutral-500">Loading…</p>
            ) : findings.length === 0 ? (
              <p className="text-sm text-neutral-500">No findings recorded yet.</p>
            ) : (
              findings.map((f) => (
                <div key={f.id} className="rounded-lg border border-neutral-800 bg-neutral-900/40 overflow-hidden flex">
                  <img src={imageUrl(f.image_file)} alt={f.finding_type} className="w-28 h-28 object-cover" />
                  <div className="p-3 text-xs flex-1 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-sm">{f.finding_type}</span>
                      <SeverityBadge severity={f.severity} />
                      <VerifierBadge outcome={f.verifier_outcome} />
                    </div>
                    <p className="text-neutral-400">{f.location_description}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-neutral-500">waypoint {f.waypoint_id}</span>
                      <Confidence value={f.confidence} />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      {report && (
        <section>
          <h2 className="text-sm font-medium text-neutral-400 mb-2">Inspection report (CrewAI Analyst + Report Writer)</h2>
          <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
            {report.report_summary && Object.keys(report.report_summary).length > 0 && (
              <div className="text-xs text-neutral-400">
                <span className="text-neutral-500">independently pandas-computed summary (ground truth, not the LLM&apos;s): </span>
                <code className="text-neutral-300">{JSON.stringify(report.report_summary)}</code>
              </div>
            )}
            <pre className="text-sm text-neutral-200 whitespace-pre-wrap">{report.report_text}</pre>
          </div>
        </section>
      )}
    </div>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, type PendingApproval } from "@/lib/api";
import { RiskBadge } from "@/components/Badges";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<PendingApproval[] | null>(null);
  const [operatorId, setOperatorId] = useState("operator-1");
  const [busyId, setBusyId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.getPendingApprovals().then(setApprovals).catch(() => setApprovals([]));
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function decide(a: PendingApproval, decision: "approved" | "rejected") {
    setBusyId(a.id);
    try {
      await api.decide(a.mission_id, decision, operatorId);
      refresh();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Approval queue</h1>
        <div>
          <label className="text-xs text-neutral-400 mr-2">Operator id</label>
          <input
            value={operatorId}
            onChange={(e) => setOperatorId(e.target.value)}
            className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm w-36"
          />
        </div>
      </div>

      {approvals === null ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : approvals.length === 0 ? (
        <p className="text-sm text-neutral-500">Nothing pending — high-risk actions will appear here (SOP-004).</p>
      ) : (
        <div className="space-y-3">
          {approvals.map((a) => (
            <div key={a.id} className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <RiskBadge level={a.risk_level} />
                    <span className="text-xs text-neutral-500">proposed by {a.proposing_agent}</span>
                  </div>
                  <p className="text-sm">{a.action_description}</p>
                  <Link href={`/missions/${a.mission_id}`} className="text-xs text-sky-400 hover:underline">
                    view mission →
                  </Link>
                </div>
                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => decide(a, "approved")}
                    disabled={busyId === a.id}
                    className="rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-3 py-1.5 text-sm text-white"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => decide(a, "rejected")}
                    disabled={busyId === a.id}
                    className="rounded bg-red-700 hover:bg-red-600 disabled:opacity-50 px-3 py-1.5 text-sm text-white"
                  >
                    Reject
                  </button>
                </div>
              </div>
              <details className="mt-2">
                <summary className="text-xs text-neutral-500 cursor-pointer">evidence</summary>
                <pre className="mt-1 text-xs text-neutral-400 whitespace-pre-wrap break-all bg-neutral-950 rounded p-2">
                  {JSON.stringify(a.evidence, null, 2)}
                </pre>
              </details>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

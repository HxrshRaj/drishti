"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, imageUrl, type Finding } from "@/lib/api";
import { SeverityBadge, VerifierBadge, Confidence } from "@/components/Badges";

export default function FindingsPage() {
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");

  useEffect(() => {
    api.listAllFindings().then(setFindings).catch(() => setFindings([]));
  }, []);

  const filtered = findings?.filter((f) => severityFilter === "all" || f.severity === severityFilter) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Findings gallery</h1>
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="rounded border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm"
        >
          <option value="all">All severities</option>
          <option value="critical">Critical</option>
          <option value="major">Major</option>
          <option value="minor">Minor</option>
          <option value="informational">Informational</option>
        </select>
      </div>

      {findings === null ? (
        <p className="text-sm text-neutral-500">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-neutral-500">No findings yet — run a mission from the Missions page.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((f) => (
            <Link
              key={f.id}
              href={`/missions/${f.mission_id}`}
              className="rounded-lg border border-neutral-800 bg-neutral-900/40 overflow-hidden hover:border-neutral-600 transition-colors"
            >
              <img src={imageUrl(f.image_file)} alt={f.finding_type} className="w-full h-40 object-cover" />
              <div className="p-3 space-y-1.5 text-xs">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-medium text-sm">{f.finding_type}</span>
                  <SeverityBadge severity={f.severity} />
                </div>
                <p className="text-neutral-400 line-clamp-2">{f.location_description}</p>
                <div className="flex items-center justify-between pt-1">
                  <VerifierBadge outcome={f.verifier_outcome} />
                  <Confidence value={f.confidence} />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

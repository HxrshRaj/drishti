"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { api, type Mission, type Site } from "@/lib/api";

const STATUS_STYLES: Record<string, string> = {
  completed: "text-emerald-400",
  running: "text-sky-400",
  awaiting_approval: "text-amber-400",
  planned: "text-neutral-400",
  failed: "text-red-400",
};

export default function MissionsPage() {
  const [missions, setMissions] = useState<Mission[] | null>(null);
  const [sites, setSites] = useState<Site[] | null>(null);
  const [siteId, setSiteId] = useState("");
  const [goal, setGoal] = useState("Routine inspection sweep");
  const [maxWaypoints, setMaxWaypoints] = useState(3);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api.listMissions().then(setMissions).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    refresh();
    api
      .listSites()
      .then((s) => {
        setSites(s);
        if (s.length > 0) setSiteId(s[0].site_id);
      })
      .catch((e) => setError(String(e)));
  }, [refresh]);

  async function handleStart() {
    if (!siteId) return;
    setStarting(true);
    setError(null);
    try {
      const result = await api.startMission(siteId, goal, maxWaypoints);
      refresh();
      window.location.href = `/missions/${result.mission_id}`;
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
        <h2 className="text-lg font-medium mb-4">Start a mission</h2>
        {sites === null ? (
          <p className="text-sm text-neutral-500">Loading sites from the simulated drone gateway…</p>
        ) : sites.length === 0 ? (
          <p className="text-sm text-red-400">No sites returned by the drone gateway — is it running?</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-[1fr_2fr_auto_auto] items-end">
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Site</label>
              <select
                value={siteId}
                onChange={(e) => setSiteId(e.target.value)}
                className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm"
              >
                {sites.map((s) => (
                  <option key={s.site_id} value={s.site_id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Operator goal</label>
              <input
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-neutral-400 mb-1">Waypoints</label>
              <input
                type="number"
                min={1}
                max={10}
                value={maxWaypoints}
                onChange={(e) => setMaxWaypoints(Number(e.target.value))}
                className="w-20 rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 text-sm"
              />
            </div>
            <button
              onClick={handleStart}
              disabled={starting}
              className="rounded bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-1.5 text-sm font-medium text-white"
            >
              {starting ? "Starting…" : "Start mission"}
            </button>
          </div>
        )}
        <p className="mt-3 text-xs text-neutral-500">
          Each waypoint runs a real VLM call and a real AutoGen verifier exchange — CPU inference, so this can take
          a while per waypoint. See the Metrics page for measured latency.
        </p>
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      </section>

      <section>
        <h2 className="text-lg font-medium mb-3">Missions</h2>
        {missions === null ? (
          <p className="text-sm text-neutral-500">Loading…</p>
        ) : missions.length === 0 ? (
          <p className="text-sm text-neutral-500">No missions yet — start one above.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-neutral-800">
            <table className="w-full text-sm">
              <thead className="bg-neutral-900/60 text-neutral-400 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">Site</th>
                  <th className="px-3 py-2 font-medium">Goal</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {missions.map((m) => (
                  <tr key={m.id} className="border-t border-neutral-800 hover:bg-neutral-900/40">
                    <td className="px-3 py-2">
                      <Link href={`/missions/${m.id}`} className="text-sky-400 hover:underline">
                        {m.site_id}
                      </Link>
                    </td>
                    <td className="px-3 py-2 text-neutral-300">{m.operator_goal}</td>
                    <td className={`px-3 py-2 font-medium ${STATUS_STYLES[m.status] ?? ""}`}>{m.status}</td>
                    <td className="px-3 py-2 text-neutral-500">{new Date(m.started_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

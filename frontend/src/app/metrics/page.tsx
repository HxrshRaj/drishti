"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Manifest = Record<string, boolean>;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-5">
      <h2 className="text-sm font-medium text-neutral-400 mb-3">{title}</h2>
      {children}
    </section>
  );
}

function NotRunYet({ command }: { command: string }) {
  return (
    <p className="text-sm text-neutral-500">
      Not generated yet. Run:{" "}
      <code className="bg-neutral-950 rounded px-1.5 py-0.5 text-xs">{command}</code>
    </p>
  );
}

export default function MetricsPage() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [retrieval, setRetrieval] = useState<Record<string, unknown> | null>(null);
  const [perception, setPerception] = useState<Record<string, unknown> | null>(null);
  const [parity, setParity] = useState<Record<string, unknown> | null>(null);
  const [bench, setBench] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.getMetricsManifest().then(setManifest).catch(() => setManifest({}));
  }, []);

  useEffect(() => {
    if (!manifest) return;
    if (manifest["retrieval_eval.json"]) api.getRetrievalEval().then(setRetrieval).catch(() => {});
    if (manifest["perception_eval.json"]) api.getPerceptionEval().then(setPerception).catch(() => {});
    if (manifest["parity_report.json"]) api.getParityReport().then(setParity).catch(() => {});
    if (manifest["bench_results.json"]) api.getBench().then(setBench).catch(() => {});
  }, [manifest]);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Metrics</h1>
      <p className="text-sm text-neutral-500 -mt-3">
        Every number below is read live from a JSON file this project's own benchmark/eval scripts wrote after a
        real run — nothing here is hand-entered. See <code>docs/benchmarks.md</code> and{" "}
        <code>docs/bias-report.md</code> for the full write-up.
      </p>

      <Section title="Perception accuracy (VLM eval)">
        {manifest && !manifest["perception_eval.json"] ? (
          <NotRunYet command="python benchmarks/eval_perception.py --n 40" />
        ) : perception ? (
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <Stat label="images" value={String(perception.n_images)} />
            <Stat label="overall accuracy" value={pct(perception.overall_accuracy as number)} />
            <Stat label="parse failure rate" value={pct(perception.parse_failure_rate as number)} />
            <Stat label="device" value={String(perception.device)} />
            <Stat label="latency p50" value={`${Math.round(perception.latency_ms_p50 as number)} ms`} />
            <Stat label="latency p95" value={`${Math.round(perception.latency_ms_p95 as number)} ms`} />
          </dl>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </Section>

      <Section title="Retrieval quality (recall@k over the SOP corpus)">
        {manifest && !manifest["retrieval_eval.json"] ? (
          <NotRunYet command="python benchmarks/eval_retrieval.py" />
        ) : retrieval ? (
          <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <Stat label="queries" value={String(retrieval.n_queries)} />
            <Stat label="SOP chunks" value={String(retrieval.n_sop_chunks)} />
            {Object.entries((retrieval.recall_at_k as Record<string, number>) ?? {}).map(([k, v]) => (
              <Stat key={k} label={`recall@${k}`} value={pct(v)} />
            ))}
          </dl>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </Section>

      <Section title="Parity report (performance across imagery conditions, SOP-011)">
        {manifest && !manifest["parity_report.json"] ? (
          <NotRunYet command="python benchmarks/build_parity_report.py" />
        ) : parity ? (
          <div className="space-y-3">
            <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
              <Stat label="n total" value={String(parity.n_total)} />
              <Stat label="overall accuracy" value={pct(parity.overall_accuracy as number)} />
              <Stat label="gap threshold" value={`${parity.gap_threshold_pp} pp`} />
            </dl>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-neutral-500 text-left">
                  <tr>
                    <th className="pr-4 py-1">group</th>
                    <th className="pr-4 py-1">value</th>
                    <th className="pr-4 py-1">n</th>
                    <th className="pr-4 py-1">accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {((parity.group_results as Record<string, unknown>[]) ?? []).map((g, i) => (
                    <tr key={i} className="border-t border-neutral-800">
                      <td className="pr-4 py-1 text-neutral-400">{String(g.group_key)}</td>
                      <td className="pr-4 py-1">{String(g.group_value)}</td>
                      <td className="pr-4 py-1">{String(g.n)}</td>
                      <td className="pr-4 py-1">
                        {pct(g.accuracy as number)}
                        {g.low_confidence_note ? <span className="text-neutral-600"> (low sample)</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {((parity.flags as unknown[]) ?? []).length > 0 ? (
              <p className="text-sm text-red-400">
                {(parity.flags as unknown[]).length} group(s) flagged — see docs/bias-report.md.
              </p>
            ) : (
              <p className="text-sm text-emerald-400">No groups flagged above the gap threshold with sufficient samples.</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </Section>

      <Section title="Latency / throughput benchmark">
        {manifest && !manifest["bench_results.json"] ? (
          <NotRunYet command="python benchmarks/run_bench.py" />
        ) : bench ? (
          <pre className="text-xs text-neutral-400 whitespace-pre-wrap overflow-x-auto">{JSON.stringify(bench, null, 2)}</pre>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </Section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-neutral-500">{label}</dt>
      <dd className="text-lg font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function pct(v: number | undefined) {
  if (v === undefined || Number.isNaN(v)) return "—";
  return `${Math.round(v * 1000) / 10}%`;
}

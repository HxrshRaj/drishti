const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-red-700/50 bg-red-950/40 text-red-300",
  major: "border-orange-700/50 bg-orange-950/40 text-orange-300",
  minor: "border-yellow-700/50 bg-yellow-950/40 text-yellow-300",
  informational: "border-neutral-700 bg-neutral-800/60 text-neutral-300",
};

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.informational;
  return <span className={`inline-block rounded px-2 py-0.5 text-xs border ${cls}`}>{severity}</span>;
}

const VERIFIER_STYLES: Record<string, string> = {
  agree: "border-emerald-700/50 bg-emerald-950/40 text-emerald-300",
  disagree: "border-red-700/50 bg-red-950/40 text-red-300",
  uncertain: "border-yellow-700/50 bg-yellow-950/40 text-yellow-300",
  unverified: "border-neutral-700 bg-neutral-800/60 text-neutral-400",
};

export function VerifierBadge({ outcome }: { outcome: string }) {
  const cls = VERIFIER_STYLES[outcome] ?? VERIFIER_STYLES.unverified;
  return <span className={`inline-block rounded px-2 py-0.5 text-xs border ${cls}`}>verifier: {outcome}</span>;
}

const RISK_STYLES: Record<string, string> = {
  high: "border-red-700/50 bg-red-950/40 text-red-300",
  medium: "border-orange-700/50 bg-orange-950/40 text-orange-300",
  low: "border-neutral-700 bg-neutral-800/60 text-neutral-300",
};

export function RiskBadge({ level }: { level: string }) {
  const cls = RISK_STYLES[level] ?? RISK_STYLES.low;
  return <span className={`inline-block rounded px-2 py-0.5 text-xs border ${cls}`}>{level} risk</span>;
}

export function Confidence({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct < 55 ? "bg-red-500" : pct < 75 ? "bg-yellow-500" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-2 w-28">
      <div className="h-1.5 flex-1 rounded-full bg-neutral-800 overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-neutral-400 tabular-nums">{pct}%</span>
    </div>
  );
}

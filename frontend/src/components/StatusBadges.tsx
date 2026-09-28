import { INFERENCE_MODE } from "@/lib/api";

export function StatusBadges() {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-700/50 bg-amber-950/40 px-2.5 py-1 text-amber-300">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        Simulated fleet
      </span>
      <span
        className={
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 " +
          (INFERENCE_MODE === "live"
            ? "border-emerald-700/50 bg-emerald-950/40 text-emerald-300"
            : "border-sky-700/50 bg-sky-950/40 text-sky-300")
        }
      >
        <span className={"h-1.5 w-1.5 rounded-full " + (INFERENCE_MODE === "live" ? "bg-emerald-400" : "bg-sky-400")} />
        {INFERENCE_MODE === "live" ? "Live inference" : "Replay (cached inference)"}
      </span>
    </div>
  );
}

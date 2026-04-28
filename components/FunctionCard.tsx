import type { Finding } from "@/lib/types";

export function FunctionCard({ finding }: { finding: Finding }) {
  const tone = finding.confidence === "confirmed" ? "text-zm-success" : "text-zm-warning";

  return (
    <div className="rounded-lg border border-zm-primary/30 bg-zm-surface p-3">
      <div className="flex items-center justify-between">
        <p className="font-semibold text-zm-text">{finding.name}</p>
        <span className={`text-xs uppercase ${tone}`}>{finding.confidence}</span>
      </div>
      <p className="mt-1 text-xs text-zm-muted">{finding.type}</p>
      <p className="mt-2 text-sm text-zm-text/90">{finding.evidence}</p>
    </div>
  );
}

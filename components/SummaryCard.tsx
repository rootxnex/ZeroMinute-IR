export function SummaryCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="zm-panel p-4">
      <p className="text-xs uppercase tracking-wide text-zm-muted">{title}</p>
      <p className="mt-2 break-all text-sm text-zm-text">{value}</p>
    </div>
  );
}

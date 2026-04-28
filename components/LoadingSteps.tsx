const STEPS = [
  "Validating contract",
  "Fetching verified source",
  "Extracting emergency controls",
  "Generating playbook",
];

export function LoadingSteps({ current }: { current: number }) {
  return (
    <div className="zm-panel p-4">
      <p className="mb-3 text-sm text-zm-muted">Analysis Progress</p>
      <div className="space-y-2">
        {STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-2 text-sm">
            <span
              className={
                i <= current ? "h-2 w-2 rounded-full bg-zm-primary" : "h-2 w-2 rounded-full bg-zm-muted/50"
              }
            />
            <span className={i <= current ? "text-zm-text" : "text-zm-muted"}>{step}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

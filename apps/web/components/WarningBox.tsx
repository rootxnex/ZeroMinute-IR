type Props = {
  warnings: string[];
  manualChecks: string[];
};

export function WarningBox({ warnings, manualChecks }: Props) {
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-zm-danger/60 bg-zm-danger/10 p-4">
        <p className="text-sm font-semibold text-zm-danger">Warnings</p>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm text-zm-text">
          {warnings.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div className="rounded-xl border border-zm-warning/60 bg-zm-warning/10 p-4">
        <p className="text-sm font-semibold text-zm-warning">Manual Verification</p>
        <ul className="mt-2 list-disc space-y-1 pl-6 text-sm text-zm-text">
          {manualChecks.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

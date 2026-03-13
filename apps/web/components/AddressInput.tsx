type Props = {
  value: string;
  onChange: (value: string) => void;
};

export function AddressInput({ value, onChange }: Props) {
  return (
    <label className="block space-y-2">
      <span className="text-sm text-zm-muted">Contract Address</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="0x..."
        className="w-full rounded-lg border border-zm-primary/30 bg-zm-surface2 px-3 py-2 text-zm-text placeholder:text-zm-muted/70 outline-none transition focus:border-zm-primary focus:shadow-zm-glow"
      />
    </label>
  );
}

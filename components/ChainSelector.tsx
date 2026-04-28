import { CHAINS } from "@/lib/constants";

type Props = {
  value: number;
  onChange: (value: number) => void;
};

export function ChainSelector({ value, onChange }: Props) {
  return (
    <label className="block space-y-2">
      <span className="text-sm text-zm-muted">Chain</span>
      <select
        className="w-full rounded-lg border border-zm-primary/30 bg-zm-surface2 px-3 py-2 text-zm-text outline-none transition focus:border-zm-primary focus:shadow-zm-glow"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {CHAINS.map((chain) => (
          <option key={chain.id} value={chain.id}>
            {chain.name}
          </option>
        ))}
      </select>
    </label>
  );
}

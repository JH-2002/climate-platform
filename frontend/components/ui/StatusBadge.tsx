export type BadgeTone = "ok" | "warn" | "error" | "unknown";

const STYLES: Record<BadgeTone, { symbol: string; className: string }> = {
  ok: { symbol: "✓", className: "border-status-ok/40 bg-status-ok/10 text-status-ok" },
  warn: { symbol: "!", className: "border-status-warn/40 bg-status-warn/10 text-status-warn" },
  error: { symbol: "✕", className: "border-status-error/40 bg-status-error/10 text-status-error" },
  unknown: {
    symbol: "?",
    className: "border-status-unknown/40 bg-status-unknown/10 text-status-unknown",
  },
};

interface StatusBadgeProps {
  tone: BadgeTone;
  /** Texto visível — o estado nunca é comunicado só pela cor. */
  label: string;
}

export function StatusBadge({ tone, label }: StatusBadgeProps) {
  const style = STYLES[tone];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-sm font-medium ${style.className}`}
    >
      <span aria-hidden="true">{style.symbol}</span>
      {label}
    </span>
  );
}

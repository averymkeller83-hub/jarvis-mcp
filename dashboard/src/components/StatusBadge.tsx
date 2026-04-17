const VARIANTS: Record<string, { dot: string; badge: string }> = {
  running: {
    dot: "bg-success shadow-[0_0_6px_rgba(52,211,153,0.5)]",
    badge: "bg-success-muted text-success border-success/20",
  },
  pending: {
    dot: "bg-warning shadow-[0_0_6px_rgba(251,191,36,0.5)]",
    badge: "bg-warning-muted text-warning border-warning/20",
  },
  error: {
    dot: "bg-danger shadow-[0_0_6px_rgba(248,113,113,0.5)]",
    badge: "bg-danger-muted text-danger border-danger/20",
  },
  stopped: {
    dot: "bg-text-muted",
    badge: "bg-surface text-text-secondary border-border-subtle",
  },
};

interface Props {
  status: string;
}

export function StatusBadge({ status }: Props) {
  const variant = VARIANTS[status] ?? VARIANTS.stopped;
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${variant.badge}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${variant.dot}`} />
      {status}
    </span>
  );
}

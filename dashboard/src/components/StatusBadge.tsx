const COLORS: Record<string, string> = {
  running: "bg-success/15 text-success",
  pending: "bg-warning/15 text-warning",
  error: "bg-danger/15 text-danger",
  stopped: "bg-gray-500/15 text-gray-400",
};

interface Props {
  status: string;
}

export function StatusBadge({ status }: Props) {
  const cls = COLORS[status] ?? COLORS.stopped;
  return (
    <span
      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${cls}`}
    >
      {status}
    </span>
  );
}

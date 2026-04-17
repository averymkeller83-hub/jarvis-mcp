import { useState, useCallback, useMemo } from "react";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { fetchEventHistory, type HistoryEvent } from "../api/events";

/* ── Event label map ─────────────────────────────────────────────── */

const EVENT_LABELS: Record<string, string> = {
  "chat.message": "Chat message sent",
  "chat.incoming": "Incoming message",
  "chat.response": "Response generated",
  "briefing.generated": "Briefing compiled",
  "briefing.delivered": "Briefing delivered",
  "scout.discovery": "Scout discovery",
  "scout_new_finds": "Scout — new finds",
  "scout.scan_complete": "Scout scan complete",
  "setup.step_completed": "Setup step completed",
  "setup.finished": "Setup finished",
  "control.executed": "Control action executed",
  "agent.started": "Agent started",
  "agent.stopped": "Agent stopped",
  "agent.completed": "Agent task completed",
  "agent.error": "Agent error",
  "error": "System error",
};

/* ── Source → color mapping ──────────────────────────────────────── */

const SOURCE_COLORS: Record<string, { badge: string; dot: string }> = {
  chat:     { badge: "bg-accent/15 text-accent",     dot: "bg-accent" },
  scout:    { badge: "bg-blue-muted text-blue",       dot: "bg-blue" },
  briefing: { badge: "bg-success-muted text-success", dot: "bg-success" },
  agent:    { badge: "bg-warning-muted text-warning", dot: "bg-warning" },
  setup:    { badge: "bg-accent/15 text-accent",      dot: "bg-accent" },
  control:  { badge: "bg-blue-muted text-blue",       dot: "bg-blue" },
  error:    { badge: "bg-danger-muted text-danger",    dot: "bg-danger" },
};

const DEFAULT_COLOR = { badge: "bg-elevated text-text-secondary", dot: "bg-text-muted" };

function sourceColor(source: string, event: string): { badge: string; dot: string } {
  if (event.includes("error")) return SOURCE_COLORS["error"] ?? DEFAULT_COLOR;
  return SOURCE_COLORS[source] ?? DEFAULT_COLOR;
}

/* ── Relative-time formatter ─────────────────────────────────────── */

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1_000);
  if (secs < 10) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

/* ── HH:MM formatter ─────────────────────────────────────────────── */

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/* ── Expandable row component ────────────────────────────────────── */

function EventRow({ evt, index }: { evt: HistoryEvent; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const hasData = Object.keys(evt.data).length > 0;
  const colors = sourceColor(evt.source, evt.event);

  return (
    <div
      className="animate-slide-up opacity-0 fill-mode-forwards"
      style={{ animationDelay: `${index * 40}ms` }}
    >
      {/* Main row */}
      <div className="flex items-start gap-4 group">
        {/* Timestamp column */}
        <span className="font-mono text-xs text-text-muted w-12 shrink-0 pt-0.5 text-right tabular-nums">
          {formatTime(evt.timestamp)}
        </span>

        {/* Timeline rail + dot */}
        <div className="flex flex-col items-center shrink-0">
          <span
            className={`block w-2.5 h-2.5 rounded-full ring-2 ring-surface ${colors.dot} shrink-0 mt-1`}
          />
          {/* Connector line is handled by the parent container */}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 pb-6">
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Source badge */}
            <span
              className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-0.5 rounded-full ${colors.badge}`}
            >
              {evt.source}
            </span>

            {/* Event label */}
            <span className="text-sm text-text-primary font-medium truncate">
              {EVENT_LABELS[evt.event] ?? evt.event}
            </span>

            {/* Spacer */}
            <span className="flex-1" />

            {/* Relative time */}
            <span className="text-[11px] text-text-muted font-mono whitespace-nowrap tabular-nums">
              {relativeTime(evt.timestamp)}
            </span>

            {/* Expand toggle */}
            {hasData && (
              <button
                onClick={() => setExpanded((p) => !p)}
                className="text-text-muted hover:text-text-secondary transition-colors ml-1"
                aria-label={expanded ? "Collapse details" : "Expand details"}
              >
                <svg
                  className={`w-3.5 h-3.5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
          </div>

          {/* Expandable data section */}
          {expanded && hasData && (
            <div className="mt-2.5 bg-void/60 border border-border-subtle rounded-lg px-3 py-2.5 animate-fade-in">
              <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
                {Object.entries(evt.data).map(([key, value]) => (
                  <div key={key} className="contents">
                    <span className="text-[11px] font-mono text-text-muted whitespace-nowrap">
                      {key}
                    </span>
                    <span className="text-[11px] font-mono text-text-secondary truncate">
                      {typeof value === "object" ? JSON.stringify(value) : String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Empty state ─────────────────────────────────────────────────── */

function EmptyState() {
  return (
    <Card className="!py-16">
      <div className="flex flex-col items-center gap-4 animate-fade-in">
        {/* Minimal radar / pulse illustration */}
        <div className="relative w-20 h-20">
          <div className="absolute inset-0 rounded-full border border-border-subtle" />
          <div className="absolute inset-2.5 rounded-full border border-border-subtle" />
          <div className="absolute inset-5 rounded-full border border-border-subtle" />
          <div className="absolute inset-[1.85rem] rounded-full bg-accent/20" />
          <div className="absolute inset-[2.1rem] rounded-full bg-accent/40 animate-pulse" />
        </div>
        <div className="text-center">
          <p className="text-text-primary font-display font-semibold text-sm">
            No activity recorded
          </p>
          <p className="text-text-muted text-xs mt-1 max-w-[260px]">
            Events will appear here as you chat, run briefings, trigger scouts, and interact with agents.
          </p>
        </div>
      </div>
    </Card>
  );
}

/* ── Main Activity page ──────────────────────────────────────────── */

export function Activity() {
  const [sourceFilter, setSourceFilter] = useState<string>("");

  const fetcher = useCallback(
    () =>
      fetchEventHistory(sourceFilter || undefined, 100).then(
        (r) => r.events,
      ),
    [sourceFilter],
  );

  const { data: events } = usePolling(fetcher, 5_000);

  const sources = useMemo(() => {
    if (!events) return [];
    const set = new Set(events.map((e: HistoryEvent) => e.source));
    return Array.from(set).sort();
  }, [events]);

  /* Events in reverse-chronological order */
  const sorted = useMemo(
    () =>
      events
        ? [...events].sort(
            (a, b) =>
              new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
          )
        : [],
    [events],
  );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-display font-bold text-text-primary tracking-tight">
            Activity
          </h1>
          <p className="text-text-muted text-xs mt-1">
            {sorted.length > 0
              ? `${sorted.length} event${sorted.length !== 1 ? "s" : ""} recorded`
              : "System event log"}
          </p>
        </div>

        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="input-base text-sm min-w-[140px]"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {/* Timeline */}
      {sorted.length > 0 ? (
        <div className="relative">
          {/* Vertical timeline line */}
          <div
            className="absolute left-[4.05rem] top-3 bottom-0 w-px bg-gradient-to-b from-accent/40 via-border-subtle to-transparent pointer-events-none"
            aria-hidden
          />

          {sorted.map((evt, i) => (
            <EventRow key={`${evt.timestamp}-${evt.event}-${i}`} evt={evt} index={i} />
          ))}
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}

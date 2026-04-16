import { useState, useCallback, useMemo } from "react";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { fetchEventHistory, type HistoryEvent } from "../api/events";

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

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Activity</h1>
        <select
          value={sourceFilter}
          onChange={(e) => setSourceFilter(e.target.value)}
          className="bg-primary border border-border-default rounded-lg px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none"
        >
          <option value="">All sources</option>
          {sources.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        {events?.map((evt: HistoryEvent, i: number) => (
          <Card key={i} className="!p-3">
            <div className="flex items-center gap-3">
              <span className="text-xs text-text-secondary font-mono whitespace-nowrap">
                {new Date(evt.timestamp).toLocaleTimeString()}
              </span>
              <span className="text-xs bg-accent/15 text-accent px-2 py-0.5 rounded-full">
                {evt.source}
              </span>
              <span className="text-sm text-text-primary font-medium">
                {evt.event}
              </span>
            </div>
            {Object.keys(evt.data).length > 0 && (
              <pre className="mt-2 text-xs text-text-secondary bg-primary p-2 rounded overflow-auto max-h-24">
                {JSON.stringify(evt.data, null, 2)}
              </pre>
            )}
          </Card>
        ))}
      </div>

      {(!events || events.length === 0) && (
        <Card>
          <p className="text-text-secondary text-center py-8">
            No events recorded yet. Activity will appear here as agents run.
          </p>
        </Card>
      )}
    </div>
  );
}

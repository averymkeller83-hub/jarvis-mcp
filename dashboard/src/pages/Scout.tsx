import { useState, useCallback } from "react";
import { Card } from "../components/Card";
import { useToast } from "../components/Toast";
import {
  fetchScoutSources,
  runDiscovery,
  installCandidate,
  dismissCandidate,
  type ScoutFind,
  type ScoutSource,
} from "../api/scout";
import { usePolling } from "../hooks/usePolling";

export function Scout() {
  const { toast } = useToast();
  const [finds, setFinds] = useState<ScoutFind[]>([]);
  const [scanning, setScanning] = useState(false);

  const sourcesFetcher = useCallback(
    () => fetchScoutSources().then((r) => r.sources),
    [],
  );
  const { data: sources } = usePolling(sourcesFetcher, 0, true);

  async function handleScan() {
    setScanning(true);
    try {
      const result = await runDiscovery();
      setFinds(result.finds);
      toast(`Found ${result.finds.length} discoveries`);
    } catch {
      toast("Scout scan failed", "error");
    } finally {
      setScanning(false);
    }
  }

  async function handleInstall(candidateId: string) {
    try {
      await installCandidate(candidateId);
      setFinds((prev) => prev.filter((f) => f.candidate_id !== candidateId));
      toast("Installed");
    } catch {
      toast("Install failed", "error");
    }
  }

  async function handleDismiss(candidateId: string) {
    try {
      await dismissCandidate(candidateId);
      setFinds((prev) => prev.filter((f) => f.candidate_id !== candidateId));
      toast("Dismissed");
    } catch {
      toast("Dismiss failed", "error");
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Scout</h1>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="bg-accent hover:bg-accent-hover text-white font-semibold px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          {scanning ? "Scanning..." : "Scan Now"}
        </button>
      </div>

      {sources && sources.length > 0 && (
        <Card className="mb-6">
          <h2 className="text-sm text-text-secondary uppercase tracking-wider mb-3">
            Sources
          </h2>
          <div className="flex flex-wrap gap-2">
            {sources.map((s: ScoutSource) => (
              <span
                key={s.name}
                className={`text-xs px-2.5 py-1 rounded-full border ${
                  s.enabled
                    ? "border-success/30 text-success"
                    : "border-border-default text-text-secondary"
                }`}
              >
                {s.name}
              </span>
            ))}
          </div>
        </Card>
      )}

      <div className="space-y-4">
        {finds.map((find) => (
          <Card key={find.candidate_id}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-text-primary">
                    {find.title}
                  </h3>
                  <span className="text-xs bg-accent/15 text-accent px-2 py-0.5 rounded-full">
                    {Math.round(find.relevance * 100)}%
                  </span>
                </div>
                <p className="text-sm text-text-secondary mb-2">
                  {find.summary}
                </p>
                <p className="text-xs text-text-secondary">
                  Source: {find.source}
                </p>
              </div>
              <div className="flex gap-2 flex-shrink-0">
                <button
                  onClick={() => handleInstall(find.candidate_id)}
                  className="bg-success/20 text-success px-3 py-1.5 rounded-lg text-xs font-medium"
                >
                  Install
                </button>
                <button
                  onClick={() => handleDismiss(find.candidate_id)}
                  className="bg-card border border-border-default text-text-secondary px-3 py-1.5 rounded-lg text-xs font-medium hover:text-text-primary"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {finds.length === 0 && (
        <Card>
          <p className="text-text-secondary text-center py-8">
            No discoveries yet. Click "Scan Now" to search.
          </p>
        </Card>
      )}
    </div>
  );
}

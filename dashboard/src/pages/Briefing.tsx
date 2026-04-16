import { useState, useCallback } from "react";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { useToast } from "../components/Toast";
import { fetchBriefing } from "../api/briefing";
import { api } from "../api/client";

export function Briefing() {
  const { toast } = useToast();
  const [composing, setComposing] = useState(false);

  const fetcher = useCallback(() => fetchBriefing(), []);
  const { data: briefing, refetch } = usePolling(fetcher, 0, true);

  async function handleCompose() {
    setComposing(true);
    try {
      await api("/engine/run/briefing", { method: "POST" });
      toast("Briefing composed");
      refetch();
    } catch {
      toast("Failed to compose briefing", "error");
    } finally {
      setComposing(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Briefing</h1>
        <button
          onClick={handleCompose}
          disabled={composing}
          className="bg-accent hover:bg-accent-hover text-white font-semibold px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
        >
          {composing ? "Composing..." : "Compose Now"}
        </button>
      </div>

      {briefing?.generated_at && (
        <p className="text-text-secondary text-sm mb-4">
          Generated: {new Date(briefing.generated_at).toLocaleString()}
        </p>
      )}

      {briefing?.summary && (
        <Card className="mb-4">
          <p className="text-text-primary">{briefing.summary}</p>
        </Card>
      )}

      <div className="space-y-4">
        {briefing?.sections?.map((section, i) => (
          <Card key={i}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-text-primary">
                {section.title}
              </h3>
              <span className="text-xs text-text-secondary">
                {section.source}
              </span>
            </div>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">
              {section.content}
            </p>
          </Card>
        ))}
      </div>

      {!briefing?.sections?.length && (
        <Card>
          <p className="text-text-secondary text-center py-8">
            No briefing yet. Click "Compose Now" to generate one.
          </p>
        </Card>
      )}
    </div>
  );
}

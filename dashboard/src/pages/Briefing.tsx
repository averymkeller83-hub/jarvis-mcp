import { useState, useCallback } from "react";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { useToast } from "../components/Toast";
import { fetchBriefing } from "../api/briefing";
import { api } from "../api/client";

/* ------------------------------------------------------------------ */
/*  Icons                                                              */
/* ------------------------------------------------------------------ */

const IconSend = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const IconSpinner = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="animate-spin">
    <path d="M21 12a9 9 0 11-6.219-8.56" />
  </svg>
);

const IconDocument = (
  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  }) + " at " + d.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

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

  const hasSections = briefing?.sections && briefing.sections.length > 0;

  /* -- Render ------------------------------------------------------ */

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-display font-bold text-text-primary tracking-tight">
            Briefing
          </h1>
          {briefing?.generated_at && (
            <p className="text-text-muted text-xs font-mono mt-1.5">
              Generated {formatTimestamp(briefing.generated_at)}
            </p>
          )}
        </div>
        <button
          onClick={handleCompose}
          disabled={composing}
          className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
        >
          {composing ? IconSpinner : IconSend}
          <span>{composing ? "Composing\u2026" : "Compose Now"}</span>
        </button>
      </div>

      {/* Summary */}
      {briefing?.summary && (
        <div
          className="animate-slide-up"
          style={{ animationDelay: "0ms" }}
        >
          <Card className="mb-6 border-l-2 border-l-accent">
            <p className="text-text-primary font-body leading-relaxed">
              {briefing.summary}
            </p>
          </Card>
        </div>
      )}

      {/* Sections */}
      {hasSections && (
        <div className="space-y-4">
          {briefing.sections.map((section, i) => (
            <div
              key={`${section.title}-${i}`}
              className="animate-slide-up"
              style={{ animationDelay: `${(i + 1) * 80}ms` }}
            >
              <Card>
                <div className="flex items-start justify-between gap-4 mb-3">
                  <h3 className="font-display font-semibold text-text-primary text-base">
                    {section.title}
                  </h3>
                  <span className="shrink-0 section-title text-[10px] bg-surface px-2.5 py-1 rounded-full border border-border-subtle">
                    {section.source}
                  </span>
                </div>
                <p className="text-sm text-text-secondary font-body whitespace-pre-wrap leading-relaxed">
                  {section.content}
                </p>
              </Card>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {!hasSections && (
        <div className="animate-slide-up" style={{ animationDelay: "60ms" }}>
          <Card>
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="text-text-muted mb-4">
                {IconDocument}
              </div>
              <h3 className="text-lg font-display font-semibold text-text-primary mb-2">
                No briefing yet
              </h3>
              <p className="text-text-secondary text-sm font-body mb-6 max-w-sm">
                Compose your first briefing to get a summary of weather, calendar, news, and more.
              </p>
              <button
                onClick={handleCompose}
                disabled={composing}
                className="btn-primary inline-flex items-center gap-2 disabled:opacity-50"
              >
                {composing ? IconSpinner : IconSend}
                <span>{composing ? "Composing\u2026" : "Compose Now"}</span>
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

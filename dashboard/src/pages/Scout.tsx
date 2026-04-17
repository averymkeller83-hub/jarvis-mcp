import { useState, useEffect, useCallback } from "react";
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

/* ── Relevance meter ─────────────────────────────────────── */

function RelevanceMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80
      ? "bg-success shadow-[0_0_6px_rgba(52,211,153,0.35)]"
      : pct >= 50
        ? "bg-accent shadow-[0_0_6px_rgba(192,145,90,0.3)]"
        : "bg-warning shadow-[0_0_6px_rgba(251,191,36,0.3)]";

  return (
    <div className="flex items-center gap-2.5 min-w-[120px]">
      <div className="flex-1 h-1.5 rounded-full bg-border-subtle overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[11px] font-mono text-text-secondary tabular-nums w-8 text-right">
        {pct}%
      </span>
    </div>
  );
}

/* ── Scanning animation ──────────────────────────────────── */

function ScanningOverlay() {
  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
      {/* Radar sweep */}
      <div className="relative w-24 h-24 mb-6">
        <div className="absolute inset-0 rounded-full border border-accent/20" />
        <div className="absolute inset-3 rounded-full border border-accent/15" />
        <div className="absolute inset-6 rounded-full border border-accent/10" />
        <div className="absolute inset-0 rounded-full overflow-hidden">
          <div
            className="absolute top-1/2 left-1/2 w-1/2 h-1/2 origin-top-left animate-spin-slow"
            style={{
              background:
                "conic-gradient(from 0deg, transparent 0%, rgba(192,145,90,0.35) 30%, transparent 60%)",
            }}
          />
        </div>
        <div className="absolute inset-[44%] rounded-full bg-accent shadow-[0_0_12px_rgba(192,145,90,0.5)]" />
      </div>
      <p className="text-text-primary font-display font-semibold text-lg">
        Scanning sources...
      </p>
      <p className="text-text-secondary text-sm mt-1 font-body">
        Searching for new tools, integrations, and capabilities
      </p>
    </div>
  );
}

/* ── Empty state ─────────────────────────────────────────── */

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
      <div className="relative w-20 h-20 mb-6">
        {/* Stylized scope / crosshair */}
        <svg
          viewBox="0 0 80 80"
          fill="none"
          className="w-full h-full text-text-muted"
        >
          <circle cx="40" cy="40" r="28" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
          <circle cx="40" cy="40" r="16" stroke="currentColor" strokeWidth="1" opacity="0.25" />
          <line x1="40" y1="4" x2="40" y2="20" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
          <line x1="40" y1="60" x2="40" y2="76" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
          <line x1="4" y1="40" x2="20" y2="40" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
          <line x1="60" y1="40" x2="76" y2="40" stroke="currentColor" strokeWidth="1.5" opacity="0.3" />
          <circle cx="40" cy="40" r="3" fill="currentColor" opacity="0.2" />
        </svg>
      </div>
      <p className="text-text-primary font-display font-semibold text-lg">
        No discoveries this scan
      </p>
      <p className="text-text-secondary text-sm mt-1 font-body max-w-xs text-center">
        All clear on the radar. New tools and integrations will appear here when detected.
      </p>
    </div>
  );
}

/* ── Spinner icon ────────────────────────────────────────── */

function Spinner() {
  return (
    <svg
      className="animate-spin h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        className="opacity-20"
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/* ── Discovery card ──────────────────────────────────────── */

function DiscoveryCard({
  find,
  index,
  onInstall,
  onDismiss,
}: {
  find: ScoutFind;
  index: number;
  onInstall: (id: string) => void;
  onDismiss: (id: string) => void;
}) {
  const [acting, setActing] = useState<"install" | "dismiss" | null>(null);

  const handleInstall = useCallback(async () => {
    setActing("install");
    await onInstall(find.candidate_id);
    setActing(null);
  }, [find.candidate_id, onInstall]);

  const handleDismiss = useCallback(async () => {
    setActing("dismiss");
    await onDismiss(find.candidate_id);
    setActing(null);
  }, [find.candidate_id, onDismiss]);

  return (
    <div
      className="animate-slide-up"
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "both" }}
    >
      <Card className="group relative overflow-hidden hover:border-border-default transition-all duration-300 hover:shadow-[0_0_24px_rgba(192,145,90,0.06)]">
        {/* Subtle top-edge accent on hover */}
        <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-accent/0 to-transparent group-hover:via-accent/40 transition-all duration-500" />

        <div className="flex items-start justify-between gap-5">
          {/* Content */}
          <div className="flex-1 min-w-0">
            {/* Header row */}
            <div className="flex items-center gap-3 mb-2">
              <h3 className="font-display font-bold text-text-primary text-base truncate">
                {find.name}
              </h3>
              {find.sandbox_status === "running" && (
                <span className="flex items-center gap-1 text-[10px] font-mono text-blue-400 bg-blue-400/10 border border-blue-400/20 px-2 py-0.5 rounded-full whitespace-nowrap">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  sandbox
                </span>
              )}
            </div>

            {/* Relevance meter */}
            <div className="mb-3">
              <RelevanceMeter score={find.details.relevance_score} />
            </div>

            {/* Pitch */}
            <p className="text-sm text-text-secondary font-body leading-relaxed mb-3">
              {find.pitch}
            </p>

            {/* Match reason (if different from pitch) */}
            {find.match_reason && find.match_reason !== find.pitch && (
              <p className="text-xs text-text-muted font-body italic mb-3">
                Match: {find.match_reason}
              </p>
            )}

            {/* Pills + link row */}
            <div className="flex items-center flex-wrap gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider bg-accent/10 text-accent border border-accent/15 px-2.5 py-1 rounded-full">
                {find.source_badge}
              </span>
              <span className="text-[11px] font-medium bg-white/[0.04] text-text-secondary border border-border-subtle px-2.5 py-1 rounded-full">
                {find.details.candidate_type}
              </span>
              {find.details.source_url && (
                <a
                  href={find.details.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[11px] text-accent/80 hover:text-accent font-medium flex items-center gap-1 transition-colors ml-1"
                >
                  <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M3.75 2A1.75 1.75 0 002 3.75v8.5c0 .966.784 1.75 1.75 1.75h8.5A1.75 1.75 0 0014 12.25v-3.5a.75.75 0 00-1.5 0v3.5a.25.25 0 01-.25.25h-8.5a.25.25 0 01-.25-.25v-8.5a.25.25 0 01.25-.25h3.5a.75.75 0 000-1.5h-3.5zm6.5 0a.75.75 0 000 1.5h1.19L7.22 7.72a.75.75 0 101.06 1.06l4.22-4.22v1.19a.75.75 0 001.5 0V2.75a.75.75 0 00-.75-.75h-3z" />
                  </svg>
                  Source
                </a>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2 flex-shrink-0 pt-1">
            {find.install_available && (
              <button
                onClick={handleInstall}
                disabled={acting !== null}
                className="flex items-center justify-center gap-1.5 bg-success/10 border border-success/20 text-success
                           px-3.5 py-2 rounded-lg text-xs font-semibold
                           hover:bg-success/20 hover:border-success/30 hover:shadow-[0_0_12px_rgba(52,211,153,0.15)]
                           transition-all duration-200 active:scale-[0.97]
                           disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {acting === "install" ? (
                  <Spinner />
                ) : (
                  <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 1.5a.75.75 0 01.75.75v5h5a.75.75 0 010 1.5h-5v5a.75.75 0 01-1.5 0v-5h-5a.75.75 0 010-1.5h5v-5A.75.75 0 018 1.5z" />
                  </svg>
                )}
                Install
              </button>
            )}
            <button
              onClick={handleDismiss}
              disabled={acting !== null}
              className="btn-ghost text-xs font-medium !px-3.5 !py-2 border border-transparent
                         hover:border-border-subtle
                         disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {acting === "dismiss" ? (
                <span className="flex items-center justify-center gap-1.5">
                  <Spinner /> Dismiss
                </span>
              ) : (
                "Dismiss"
              )}
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ── Main page ───────────────────────────────────────────── */

export function Scout() {
  const { toast } = useToast();
  const [finds, setFinds] = useState<ScoutFind[]>([]);
  const [scanning, setScanning] = useState(false);
  const [hasScanned, setHasScanned] = useState(false);

  const sourcesFetcher = useCallback(
    () => fetchScoutSources().then((r) => r.sources),
    [],
  );
  const { data: sources } = usePolling(sourcesFetcher, 0, true);

  const handleScan = useCallback(async () => {
    setScanning(true);
    try {
      const result = await runDiscovery();
      setFinds(result.finds);
      setHasScanned(true);
      if (result.finds.length > 0) {
        toast(`Found ${result.finds.length} discover${result.finds.length === 1 ? "y" : "ies"}`);
      }
    } catch {
      toast("Scout scan failed", "error");
    } finally {
      setScanning(false);
    }
  }, [toast]);

  const handleInstall = useCallback(
    async (candidateId: string) => {
      try {
        await installCandidate(candidateId);
        setFinds((prev) => prev.filter((f) => f.candidate_id !== candidateId));
        toast("Candidate installed");
      } catch {
        toast("Install failed", "error");
      }
    },
    [toast],
  );

  const handleDismiss = useCallback(
    async (candidateId: string) => {
      try {
        await dismissCandidate(candidateId);
        setFinds((prev) => prev.filter((f) => f.candidate_id !== candidateId));
        toast("Candidate dismissed");
      } catch {
        toast("Dismiss failed", "error");
      }
    },
    [toast],
  );

  // Auto-scan on first mount
  useEffect(() => {
    handleScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const enabledCount = sources?.filter((s: ScoutSource) => s.enabled).length ?? 0;
  const totalCount = sources?.length ?? 0;

  return (
    <div>
      {/* ── Header ─────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold font-display text-text-primary">Scout</h1>
          <p className="text-text-secondary text-sm mt-1 font-body">
            Discover tools, integrations, and capabilities
          </p>
        </div>
        <button
          onClick={handleScan}
          disabled={scanning}
          className="btn-primary flex items-center gap-2 text-sm"
        >
          {scanning ? (
            <>
              <Spinner />
              Scanning...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                <path d="M11.742 10.344a6.5 6.5 0 10-1.397 1.398h-.001l3.85 3.85a1 1 0 001.415-1.414l-3.85-3.85-.017.016zm-5.242.156a5 5 0 110-10 5 5 0 010 10z" />
              </svg>
              Scan Now
            </>
          )}
        </button>
      </div>

      {/* ── Sources ────────────────────────────────────── */}
      {sources && sources.length > 0 && (
        <div className="mb-8 animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <h2 className="section-title">
              Sources
            </h2>
            <span className="text-[11px] font-mono text-text-muted">
              {enabledCount}/{totalCount} active
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {sources.map((s: ScoutSource) => (
              <div
                key={s.name}
                className={`
                  group/src relative flex items-center gap-2 text-xs font-medium
                  px-3 py-2 rounded-lg border transition-all duration-200
                  ${s.enabled
                    ? "border-success/20 bg-success/[0.04] text-success hover:border-success/35 hover:bg-success/[0.08]"
                    : "border-border-subtle bg-white/[0.02] text-text-muted hover:border-border-default hover:text-text-secondary"
                  }
                `}
                title={s.description}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    s.enabled
                      ? "bg-success shadow-[0_0_6px_rgba(52,211,153,0.4)]"
                      : "bg-text-muted"
                  }`}
                />
                {s.name}
                <span className="text-[10px] opacity-60 font-mono">
                  {s.cadence}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Scanning state ─────────────────────────────── */}
      {scanning && finds.length === 0 && <ScanningOverlay />}

      {/* ── Discovery cards ────────────────────────────── */}
      {!scanning && finds.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">
              Discoveries
            </h2>
            <span className="text-[11px] font-mono text-text-muted">
              {finds.length} found
            </span>
          </div>
          <div className="space-y-3">
            {finds.map((find, i) => (
              <DiscoveryCard
                key={find.candidate_id}
                find={find}
                index={i}
                onInstall={handleInstall}
                onDismiss={handleDismiss}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Empty state ────────────────────────────────── */}
      {!scanning && hasScanned && finds.length === 0 && <EmptyState />}

      {/* ── Initial loading (before first scan completes) */}
      {!scanning && !hasScanned && finds.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
          <Spinner />
          <p className="text-text-secondary text-sm mt-3 font-body">
            Initializing scanner...
          </p>
        </div>
      )}
    </div>
  );
}

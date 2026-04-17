import { useCallback } from "react";
import { Link } from "react-router-dom";
import { StatCard, LoadingCard } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { usePolling } from "../hooks/usePolling";
import { api } from "../api/client";
import { useToast } from "../components/Toast";
import { usePersonality } from "../stores/personality";
import { useAuth } from "../stores/auth";
import { checkClaudeDesktop } from "../api/auth";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface StatusData {
  daemon: string;
  agent_info?: {
    total: number;
    running: number;
    pending: number;
    error: number;
    stopped: number;
  };
}

interface HealthData {
  status: string;
  version: string;
  uptime_seconds: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function getTimeGreeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Good evening";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

/* ------------------------------------------------------------------ */
/*  Icons (inline SVGs for zero-dependency HUD feel)                   */
/* ------------------------------------------------------------------ */

const IconShield = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

const IconClock = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

const IconUsers = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 00-3-3.87" />
    <path d="M16 3.13a4 4 0 010 7.75" />
  </svg>
);

const IconAlert = (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const IconSend = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const IconRadar = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
    <line x1="12" y1="2" x2="12" y2="6" />
  </svg>
);

const IconChat = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
  </svg>
);

const IconGear = (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09a1.65 1.65 0 00-1.08-1.51 1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09a1.65 1.65 0 001.51-1.08 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001.08 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1.08z" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Dashboard                                                          */
/* ------------------------------------------------------------------ */

export function Dashboard() {
  const { toast } = useToast();
  const { userName, assistantName } = usePersonality();
  const { user } = useAuth();

  const fetchStatus = useCallback(() => api<StatusData>("/status"), []);
  const fetchHealth = useCallback(() => api<HealthData>("/health"), []);
  const fetchClaude = useCallback(() => checkClaudeDesktop(), []);

  const { data: status, loading: statusLoading } = usePolling(fetchStatus, 10_000);
  const { data: health, loading: healthLoading } = usePolling(fetchHealth, 10_000);
  const { data: claudeStatus, loading: claudeLoading } = usePolling(fetchClaude, 15_000);

  const displayName = userName || user?.username || "Sir";
  const greeting = `${getTimeGreeting()}, ${displayName}.`;
  const agents = status?.agent_info;
  const isLoading = statusLoading || healthLoading;

  /* -- Actions ---------------------------------------------------- */

  async function triggerBriefing() {
    try {
      await api("/engine/run/briefing", { method: "POST" });
      toast("Briefing composed successfully");
    } catch {
      toast("Failed to trigger briefing", "error");
    }
  }

  async function triggerScout() {
    try {
      await api("/scout/discover", { method: "POST" });
      toast("Scout scan initiated");
    } catch {
      toast("Failed to trigger scout", "error");
    }
  }

  /* -- Derived status --------------------------------------------- */

  const systemOnline = health?.status === "ok";
  const systemStatus: "online" | "warning" | "error" | "offline" = systemOnline
    ? (agents?.error ? "warning" : "online")
    : "offline";

  const uptimeStatus: "online" | "offline" = systemOnline ? "online" : "offline";

  const agentStatus: "online" | "warning" | "error" | "offline" = agents
    ? agents.error > 0
      ? "error"
      : agents.running > 0
        ? "online"
        : "offline"
    : "offline";

  const errorStatus: "online" | "warning" | "error" = agents?.error
    ? "error"
    : "online";

  /* -- Render ----------------------------------------------------- */

  return (
    <div className="animate-fade-in">
      {/* Greeting header */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-text-primary tracking-tight">
          {greeting}
        </h1>
        <p className="text-text-secondary text-sm mt-1.5 font-body">
          {assistantName} is online and at your service.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {isLoading ? (
          <>
            <LoadingCard />
            <LoadingCard />
            <LoadingCard />
            <LoadingCard />
          </>
        ) : (
          <>
            <div className="animate-slide-up" style={{ animationDelay: "0ms" }}>
              <StatCard
                label="System Status"
                value={systemOnline ? "Operational" : "Offline"}
                subtitle={health ? `v${health.version}` : "No connection"}
                status={systemStatus}
                icon={IconShield}
              />
            </div>

            <div className="animate-slide-up" style={{ animationDelay: "60ms" }}>
              <StatCard
                label="Uptime"
                value={health ? formatUptime(health.uptime_seconds) : "\u2014"}
                subtitle={systemOnline ? "since last restart" : "unavailable"}
                status={uptimeStatus}
                icon={IconClock}
              />
            </div>

            <div className="animate-slide-up" style={{ animationDelay: "120ms" }}>
              <StatCard
                label="Active Agents"
                value={agents?.total ?? 0}
                subtitle={
                  agents
                    ? `${agents.running} running \u00b7 ${agents.pending} pending`
                    : "no agents registered"
                }
                status={agentStatus}
                icon={IconUsers}
              />
            </div>

            <div className="animate-slide-up" style={{ animationDelay: "180ms" }}>
              <StatCard
                label="Errors"
                value={agents?.error ?? 0}
                subtitle={agents?.error ? "agents need attention" : "all clear"}
                status={errorStatus}
                icon={IconAlert}
              />
            </div>
          </>
        )}
      </div>

      {/* Two-column lower section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Connections */}
        <div
          className="card animate-slide-up"
          style={{ animationDelay: "240ms" }}
        >
          <h2 className="section-title mb-5">Connections</h2>
          <div className="space-y-4">
            {/* Claude Desktop */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  claudeLoading
                    ? "bg-text-muted animate-pulse"
                    : claudeStatus?.running
                      ? claudeStatus.authenticated
                        ? "bg-success shadow-[0_0_8px_rgba(52,211,153,0.6)]"
                        : "bg-warning shadow-[0_0_8px_rgba(251,191,36,0.6)]"
                      : "bg-danger shadow-[0_0_8px_rgba(248,113,113,0.5)]"
                }`} />
                <span className="text-text-primary text-sm font-body">Claude Desktop</span>
              </div>
              <span className={`text-xs font-mono font-medium px-2.5 py-1 rounded-full border ${
                claudeLoading
                  ? "bg-surface text-text-muted border-border-subtle"
                  : claudeStatus?.running
                    ? claudeStatus.authenticated
                      ? "bg-success/10 text-success border-success/20"
                      : "bg-warning/10 text-warning border-warning/20"
                    : "bg-danger/10 text-danger border-danger/20"
              }`}>
                {claudeLoading
                  ? "checking..."
                  : claudeStatus?.running
                    ? claudeStatus.authenticated
                      ? "Connected"
                      : "Not Authenticated"
                    : "Not Running"}
              </span>
            </div>

            {/* Daemon */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  healthLoading
                    ? "bg-text-muted animate-pulse"
                    : systemOnline
                      ? "bg-success shadow-[0_0_8px_rgba(52,211,153,0.6)]"
                      : "bg-danger shadow-[0_0_8px_rgba(248,113,113,0.5)]"
                }`} />
                <span className="text-text-primary text-sm font-body">{assistantName} Daemon</span>
              </div>
              <span className={`text-xs font-mono font-medium px-2.5 py-1 rounded-full border ${
                healthLoading
                  ? "bg-surface text-text-muted border-border-subtle"
                  : systemOnline
                    ? "bg-success/10 text-success border-success/20"
                    : "bg-danger/10 text-danger border-danger/20"
              }`}>
                {healthLoading
                  ? "checking..."
                  : systemOnline
                    ? "Running"
                    : "Offline"}
              </span>
            </div>

            {/* API Endpoint */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  systemOnline
                    ? "bg-accent shadow-[0_0_8px_rgba(192,145,90,0.5)]"
                    : "bg-text-muted"
                }`} />
                <span className="text-text-primary text-sm font-body">API Endpoint</span>
              </div>
              <span className="text-xs font-mono text-text-secondary">
                127.0.0.1:7900
              </span>
            </div>
          </div>

          {/* Agent breakdown (only when there are agents) */}
          {agents && agents.total > 0 && (
            <div className="mt-6 pt-5 border-t border-border-subtle">
              <h3 className="section-title mb-3">Agent Breakdown</h3>
              <div className="flex flex-wrap gap-2">
                {(["running", "pending", "error", "stopped"] as const).map((s) => {
                  const count = agents[s];
                  if (count === 0) return null;
                  return <StatusBadge key={s} status={`${count} ${s}`} />;
                })}
              </div>
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div
          className="card animate-slide-up"
          style={{ animationDelay: "300ms" }}
        >
          <h2 className="section-title mb-5">Quick Actions</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              onClick={triggerBriefing}
              className="btn-primary flex items-center justify-center gap-2.5 py-3 text-sm"
            >
              {IconSend}
              <span>Compose Briefing</span>
            </button>

            <button
              onClick={triggerScout}
              className="btn-secondary flex items-center justify-center gap-2.5 py-3 text-sm"
            >
              {IconRadar}
              <span>Run Scout</span>
            </button>

            <Link
              to="/chat"
              className="btn-ghost flex items-center justify-center gap-2.5 py-3 text-sm"
            >
              {IconChat}
              <span>Open Chat</span>
            </Link>

            <Link
              to="/settings"
              className="btn-ghost flex items-center justify-center gap-2.5 py-3 text-sm"
            >
              {IconGear}
              <span>Settings</span>
            </Link>
          </div>

          {/* Subtle system readout */}
          <div className="mt-6 pt-5 border-t border-border-subtle">
            <div className="grid grid-cols-2 gap-4 text-xs font-mono text-text-muted">
              <div>
                <span className="block text-text-secondary mb-0.5">VERSION</span>
                <span className="text-text-primary">{health?.version ?? "\u2014"}</span>
              </div>
              <div>
                <span className="block text-text-secondary mb-0.5">DAEMON</span>
                <span className="text-text-primary">{status?.daemon ?? "\u2014"}</span>
              </div>
              <div>
                <span className="block text-text-secondary mb-0.5">UPTIME</span>
                <span className="text-text-primary font-mono">
                  {health ? formatUptime(health.uptime_seconds) : "\u2014"}
                </span>
              </div>
              <div>
                <span className="block text-text-secondary mb-0.5">AGENTS</span>
                <span className="text-text-primary">{agents?.total ?? 0}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

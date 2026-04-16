import { useCallback } from "react";
import { StatCard } from "../components/Card";
import { StatusBadge } from "../components/StatusBadge";
import { usePolling } from "../hooks/usePolling";
import { api } from "../api/client";
import { useToast } from "../components/Toast";

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

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function Dashboard() {
  const { toast } = useToast();

  const fetchStatus = useCallback(() => api<StatusData>("/status"), []);
  const fetchHealth = useCallback(() => api<HealthData>("/health"), []);

  const { data: status } = usePolling(fetchStatus, 10_000);
  const { data: health } = usePolling(fetchHealth, 10_000);

  const agents = status?.agent_info;

  async function triggerBriefing() {
    try {
      await api("/engine/run/briefing", { method: "POST" });
      toast("Briefing triggered");
    } catch {
      toast("Failed to trigger briefing", "error");
    }
  }

  async function triggerScout() {
    try {
      await api("/scout/discover", { method: "POST" });
      toast("Scout scan triggered");
    } catch {
      toast("Failed to trigger scout", "error");
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Status"
          value={health?.status === "ok" ? "Healthy" : "Unknown"}
          subtitle={health ? `v${health.version}` : undefined}
        />
        <StatCard
          label="Uptime"
          value={health ? formatUptime(health.uptime_seconds) : "\u2014"}
          subtitle="since restart"
        />
        <StatCard
          label="Agents"
          value={agents?.total ?? "\u2014"}
          subtitle={
            agents
              ? `${agents.running} running, ${agents.pending} pending`
              : undefined
          }
        />
        <StatCard
          label="Errors"
          value={agents?.error ?? 0}
          subtitle={agents?.error ? "agents need attention" : "all clear"}
        />
      </div>

      {agents && agents.total > 0 && (
        <div className="bg-card border border-border-default rounded-xl p-5 mb-8">
          <h2 className="text-sm text-text-secondary uppercase tracking-wider mb-4">
            Agent Overview
          </h2>
          <div className="space-y-3">
            {(["running", "pending", "error", "stopped"] as const).map((s) => {
              const count = agents[s];
              if (count === 0) return null;
              return (
                <div key={s} className="flex items-center justify-between">
                  <StatusBadge status={s} />
                  <span className="text-text-primary font-medium">
                    {count} agent{count !== 1 ? "s" : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={triggerBriefing}
          className="bg-accent hover:bg-accent-hover text-white font-semibold px-4 py-2 rounded-lg transition-colors"
        >
          Compose Briefing
        </button>
        <button
          onClick={triggerScout}
          className="bg-card border border-border-default hover:bg-white/5 text-text-primary font-semibold px-4 py-2 rounded-lg transition-colors"
        >
          Run Scout
        </button>
      </div>
    </div>
  );
}

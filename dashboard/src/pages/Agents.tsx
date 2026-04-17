import { useState, useCallback } from "react";
import { DataTable } from "../components/DataTable";
import { StatusBadge } from "../components/StatusBadge";
import { Modal } from "../components/Modal";
import { Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { useToast } from "../components/Toast";
import {
  fetchAgents,
  fetchAgentContext,
  runAgent,
  approveAgent,
  stopAgent,
  startAgent,
  type Agent,
} from "../api/agents";

type AgentRow = Agent & Record<string, unknown>;

/* ------------------------------------------------------------------ */
/*  Icons                                                              */
/* ------------------------------------------------------------------ */

const IconPlay = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="5 3 19 12 5 21 5 3" />
  </svg>
);

const IconStop = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
  </svg>
);

const IconCheck = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
);

const IconBolt = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export function Agents() {
  const { toast } = useToast();
  const [selected, setSelected] = useState<Agent | null>(null);
  const [context, setContext] = useState<Record<string, unknown> | null>(null);
  const [loadingCtx, setLoadingCtx] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetcher = useCallback(
    () => fetchAgents().then((r) => r.agents),
    [],
  );
  const { data: agents, refetch } = usePolling(fetcher, 15_000);

  async function openDetail(agent: Agent) {
    setSelected(agent);
    setContext(null);
    setLoadingCtx(true);
    try {
      const ctx = await fetchAgentContext(agent.name);
      setContext(ctx);
    } catch {
      setContext(null);
    } finally {
      setLoadingCtx(false);
    }
  }

  async function handleAction(
    action: "run" | "approve" | "stop" | "start",
    name: string,
  ) {
    setActionLoading(action);
    try {
      if (action === "run") await runAgent(name);
      else if (action === "approve") await approveAgent(name);
      else if (action === "stop") await stopAgent(name);
      else if (action === "start") await startAgent(name);
      toast(`${action} ${name}: success`);
      refetch();
    } catch {
      toast(`${action} ${name}: failed`, "error");
    } finally {
      setActionLoading(null);
    }
  }

  /* -- Column definitions ------------------------------------------ */

  const columns = [
    {
      key: "name",
      label: "Name",
      render: (row: AgentRow) => (
        <span className="font-medium text-text-primary font-body">{row.name}</span>
      ),
    },
    {
      key: "status",
      label: "Status",
      render: (row: AgentRow) => <StatusBadge status={row.status} />,
    },
    {
      key: "type",
      label: "Type",
      render: (row: AgentRow) => (
        <span className="text-text-secondary text-sm font-body">{row.type}</span>
      ),
    },
    {
      key: "schedule",
      label: "Schedule",
      render: (row: AgentRow) => (
        <span className="text-text-secondary text-sm font-mono">
          {row.schedule ?? "\u2014"}
        </span>
      ),
    },
    {
      key: "permissions",
      label: "Permissions",
      render: (row: AgentRow) => (
        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-surface text-text-secondary text-xs font-mono border border-border-subtle">
          {row.permissions.length}
        </span>
      ),
      sortable: false,
    },
  ];

  /* -- Render ------------------------------------------------------ */

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-text-primary tracking-tight">
          Agents
        </h1>
        <p className="text-text-secondary text-sm mt-1.5 font-body">
          {agents
            ? `${agents.length} registered agent${agents.length !== 1 ? "s" : ""}`
            : "Loading agent roster\u2026"}
        </p>
      </div>

      {/* Table */}
      <Card>
        <DataTable
          columns={columns}
          data={(agents ?? []) as AgentRow[]}
          keyField="name"
          onRowClick={(row) => openDetail(row as Agent)}
          emptyMessage="No agents registered yet."
        />
      </Card>

      {/* Detail drawer */}
      <Modal
        open={!!selected}
        onClose={() => {
          setSelected(null);
          setContext(null);
        }}
        title={selected?.name ?? ""}
      >
        {selected && (
          <div className="space-y-6">
            {/* Status & type */}
            <div className="flex items-center gap-3">
              <StatusBadge status={selected.status} />
              <span className="text-text-secondary text-sm font-body">
                {selected.type}
              </span>
            </div>

            {/* Schedule */}
            {selected.schedule && (
              <div>
                <p className="section-title mb-2">Schedule</p>
                <div className="bg-primary rounded-lg border border-border-subtle px-3 py-2">
                  <p className="text-sm font-mono text-text-primary">{selected.schedule}</p>
                </div>
              </div>
            )}

            {/* Triggers */}
            {selected.triggers.length > 0 && (
              <div>
                <p className="section-title mb-2">Triggers</p>
                <div className="flex flex-wrap gap-1.5">
                  {selected.triggers.map((t) => (
                    <span
                      key={t}
                      className="text-xs font-mono bg-blue-muted text-blue px-2.5 py-1 rounded-full border border-blue/20"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Permissions */}
            <div>
              <p className="section-title mb-2">Permissions</p>
              {selected.permissions.length > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {selected.permissions.map((p) => (
                    <span
                      key={p}
                      className="text-xs font-mono bg-surface px-2.5 py-1 rounded-full border border-border-default text-text-secondary"
                    >
                      {p}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-text-muted font-body">No permissions granted.</p>
              )}
            </div>

            {/* Context */}
            <div>
              <p className="section-title mb-2">Context</p>
              {loadingCtx ? (
                <div className="bg-primary rounded-lg border border-border-subtle p-4">
                  <div className="space-y-2">
                    <div className="h-3 w-3/4 rounded bg-border-subtle loading-shimmer" />
                    <div className="h-3 w-1/2 rounded bg-border-subtle loading-shimmer" />
                    <div className="h-3 w-2/3 rounded bg-border-subtle loading-shimmer" />
                  </div>
                </div>
              ) : context && Object.keys(context).length > 0 ? (
                <pre className="text-xs font-mono bg-primary p-4 rounded-lg overflow-auto max-h-56 border border-border-subtle text-text-secondary leading-relaxed">
                  {JSON.stringify(context, null, 2)}
                </pre>
              ) : (
                <p className="text-sm text-text-muted font-body">No context available.</p>
              )}
            </div>

            {/* Actions */}
            <div className="pt-2 border-t border-border-subtle">
              <p className="section-title mb-3">Actions</p>
              <div className="flex flex-wrap gap-2">
                {selected.status === "pending" && (
                  <button
                    onClick={() => handleAction("approve", selected.name)}
                    disabled={actionLoading === "approve"}
                    className="inline-flex items-center gap-1.5 bg-success/10 text-success hover:bg-success/20 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {IconCheck}
                    {actionLoading === "approve" ? "Approving\u2026" : "Approve"}
                  </button>
                )}
                {selected.status === "running" && (
                  <button
                    onClick={() => handleAction("stop", selected.name)}
                    disabled={actionLoading === "stop"}
                    className="inline-flex items-center gap-1.5 bg-danger/10 text-danger hover:bg-danger/20 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {IconStop}
                    {actionLoading === "stop" ? "Stopping\u2026" : "Stop"}
                  </button>
                )}
                {selected.status === "stopped" && (
                  <button
                    onClick={() => handleAction("start", selected.name)}
                    disabled={actionLoading === "start"}
                    className="inline-flex items-center gap-1.5 bg-success/10 text-success hover:bg-success/20 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                  >
                    {IconPlay}
                    {actionLoading === "start" ? "Starting\u2026" : "Start"}
                  </button>
                )}
                <button
                  onClick={() => handleAction("run", selected.name)}
                  disabled={actionLoading === "run"}
                  className="inline-flex items-center gap-1.5 bg-accent/10 text-accent hover:bg-accent/20 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {IconBolt}
                  {actionLoading === "run" ? "Running\u2026" : "Run Now"}
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

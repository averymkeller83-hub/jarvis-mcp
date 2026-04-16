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

export function Agents() {
  const { toast } = useToast();
  const [selected, setSelected] = useState<Agent | null>(null);
  const [context, setContext] = useState<Record<string, unknown> | null>(null);

  const fetcher = useCallback(
    () => fetchAgents().then((r) => r.agents),
    [],
  );
  const { data: agents, refetch } = usePolling(fetcher, 15_000);

  async function openDetail(agent: Agent) {
    setSelected(agent);
    try {
      const ctx = await fetchAgentContext(agent.name);
      setContext(ctx);
    } catch {
      setContext(null);
    }
  }

  async function handleAction(
    action: "run" | "approve" | "stop" | "start",
    name: string,
  ) {
    try {
      if (action === "run") await runAgent(name);
      else if (action === "approve") await approveAgent(name);
      else if (action === "stop") await stopAgent(name);
      else if (action === "start") await startAgent(name);
      toast(`${action} ${name}: success`);
      refetch();
    } catch {
      toast(`${action} ${name}: failed`, "error");
    }
  }

  const columns = [
    {
      key: "name",
      label: "Name",
      render: (row: AgentRow) => (
        <span className="font-medium text-text-primary">{row.name}</span>
      ),
    },
    {
      key: "status",
      label: "Status",
      render: (row: AgentRow) => <StatusBadge status={row.status} />,
    },
    { key: "type", label: "Type" },
    {
      key: "schedule",
      label: "Schedule",
      render: (row: AgentRow) => (
        <span className="text-text-secondary">{row.schedule ?? "\u2014"}</span>
      ),
    },
    {
      key: "permissions",
      label: "Permissions",
      render: (row: AgentRow) => (
        <span className="text-text-secondary text-xs">
          {row.permissions.length}
        </span>
      ),
      sortable: false,
    },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Agents</h1>

      <Card>
        <DataTable
          columns={columns}
          data={(agents ?? []) as AgentRow[]}
          keyField="name"
          onRowClick={(row) => openDetail(row as Agent)}
        />
      </Card>

      <Modal
        open={!!selected}
        onClose={() => {
          setSelected(null);
          setContext(null);
        }}
        title={selected?.name ?? ""}
      >
        {selected && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <StatusBadge status={selected.status} />
              <span className="text-text-secondary text-sm">
                {selected.type}
              </span>
            </div>

            {selected.schedule && (
              <div>
                <p className="text-xs text-text-secondary uppercase mb-1">
                  Schedule
                </p>
                <p className="text-sm font-mono">{selected.schedule}</p>
              </div>
            )}

            <div>
              <p className="text-xs text-text-secondary uppercase mb-1">
                Permissions
              </p>
              <div className="flex flex-wrap gap-1">
                {selected.permissions.map((p) => (
                  <span
                    key={p}
                    className="text-xs bg-primary px-2 py-0.5 rounded border border-border-default"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>

            {context && Object.keys(context).length > 0 && (
              <div>
                <p className="text-xs text-text-secondary uppercase mb-1">
                  Context
                </p>
                <pre className="text-xs bg-primary p-3 rounded-lg overflow-auto max-h-48 border border-border-default">
                  {JSON.stringify(context, null, 2)}
                </pre>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              {selected.status === "pending" && (
                <button
                  onClick={() => handleAction("approve", selected.name)}
                  className="bg-success/20 text-success px-3 py-1.5 rounded-lg text-sm font-medium"
                >
                  Approve
                </button>
              )}
              {selected.status === "running" && (
                <button
                  onClick={() => handleAction("stop", selected.name)}
                  className="bg-danger/20 text-danger px-3 py-1.5 rounded-lg text-sm font-medium"
                >
                  Stop
                </button>
              )}
              {selected.status === "stopped" && (
                <button
                  onClick={() => handleAction("start", selected.name)}
                  className="bg-success/20 text-success px-3 py-1.5 rounded-lg text-sm font-medium"
                >
                  Start
                </button>
              )}
              <button
                onClick={() => handleAction("run", selected.name)}
                className="bg-accent/20 text-accent px-3 py-1.5 rounded-lg text-sm font-medium"
              >
                Run Now
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

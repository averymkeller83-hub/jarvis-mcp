import { useState, useEffect, useCallback } from "react";
import { Card } from "../components/Card";
import { Toggle } from "../components/Toggle";
import { useToast } from "../components/Toast";
import {
  fetchSettings,
  updateSection,
  fetchNotifications,
  updateNotifications,
  fetchControlTiers,
  updateControlTiers,
  exportData,
} from "../api/settings";

type SettingsData = Record<string, Record<string, unknown>>;

const SECTIONS = [
  "personality",
  "voice",
  "behavior",
  "communication",
  "briefing",
  "privacy",
] as const;

export function Settings() {
  const { toast } = useToast();
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [notifications, setNotifications] = useState<Record<string, unknown> | null>(null);
  const [tiers, setTiers] = useState<Record<string, unknown> | null>(null);
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const [s, n, t] = await Promise.all([
        fetchSettings(),
        fetchNotifications(),
        fetchControlTiers(),
      ]);
      setSettings(s as SettingsData);
      setNotifications(n);
      setTiers(t);
    } catch {
      toast("Failed to load settings", "error");
    }
  }, [toast]);

  useEffect(() => {
    load();
  }, [load]);

  function handleChange(section: string, key: string, value: unknown) {
    setSettings((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [section]: { ...prev[section], [key]: value },
      };
    });
    setDirty((prev) => new Set(prev).add(section));
  }

  async function handleSave(section: string) {
    if (!settings?.[section]) return;
    try {
      await updateSection(section, settings[section]);
      setDirty((prev) => {
        const next = new Set(prev);
        next.delete(section);
        return next;
      });
      toast(`${section} saved`);
    } catch {
      toast(`Failed to save ${section}`, "error");
    }
  }

  async function handleSaveNotifications() {
    if (!notifications) return;
    try {
      await updateNotifications(notifications);
      toast("Notifications saved");
    } catch {
      toast("Failed to save notifications", "error");
    }
  }

  async function handleSaveTiers() {
    if (!tiers) return;
    try {
      await updateControlTiers(tiers);
      toast("Control tiers saved");
    } catch {
      toast("Failed to save tiers", "error");
    }
  }

  async function handleExport() {
    try {
      const result = await exportData();
      toast(`Exported to ${result.path}`);
    } catch {
      toast("Export failed", "error");
    }
  }

  if (!settings) {
    return <p className="text-text-secondary">Loading settings...</p>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <button
          onClick={handleExport}
          className="bg-card border border-border-default hover:bg-white/5 text-text-primary font-semibold px-4 py-2 rounded-lg transition-colors text-sm"
        >
          Export All Data
        </button>
      </div>

      <div className="space-y-6">
        {SECTIONS.map((section) => {
          const data = settings[section];
          if (!data) return null;
          return (
            <Card key={section}>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-text-primary capitalize">
                  {section}
                </h2>
                <button
                  onClick={() => handleSave(section)}
                  disabled={!dirty.has(section)}
                  className="bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-3 py-1.5 rounded-lg transition-colors disabled:opacity-30"
                >
                  Save
                </button>
              </div>
              <div className="grid grid-cols-2 gap-4">
                {Object.entries(data).map(([key, value]) => (
                  <div key={key}>
                    <label className="block text-sm text-text-secondary mb-1 capitalize">
                      {key.replace(/_/g, " ")}
                    </label>
                    {typeof value === "boolean" ? (
                      <Toggle
                        checked={value}
                        onChange={(v) => handleChange(section, key, v)}
                      />
                    ) : (
                      <input
                        type="text"
                        value={String(value ?? "")}
                        onChange={(e) =>
                          handleChange(section, key, e.target.value)
                        }
                        className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                      />
                    )}
                  </div>
                ))}
              </div>
            </Card>
          );
        })}

        {notifications && (
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary">
                Notifications
              </h2>
              <button
                onClick={handleSaveNotifications}
                className="bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-3 py-1.5 rounded-lg transition-colors"
              >
                Save
              </button>
            </div>
            <pre className="text-xs bg-primary p-3 rounded-lg overflow-auto max-h-48 border border-border-default text-text-secondary">
              {JSON.stringify(notifications, null, 2)}
            </pre>
          </Card>
        )}

        {tiers && (
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary">
                Control Tiers
              </h2>
              <button
                onClick={handleSaveTiers}
                className="bg-accent hover:bg-accent-hover text-white text-sm font-semibold px-3 py-1.5 rounded-lg transition-colors"
              >
                Save
              </button>
            </div>
            <pre className="text-xs bg-primary p-3 rounded-lg overflow-auto max-h-48 border border-border-default text-text-secondary">
              {JSON.stringify(tiers, null, 2)}
            </pre>
          </Card>
        )}
      </div>
    </div>
  );
}

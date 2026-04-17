import { useState, useEffect, useCallback } from "react";
import { Card } from "../components/Card";
import { Toggle } from "../components/Toggle";
import { useToast } from "../components/Toast";
import { usePersonality } from "../stores/personality";
import {
  fetchSettings,
  updateSection,
  fetchNotifications,
  exportData,
} from "../api/settings";

type SettingsData = Record<string, Record<string, unknown>>;

const GENERIC_SECTIONS = ["behavior", "briefing", "privacy"] as const;

const TTS_PROVIDERS = [
  { id: "macos_say", label: "macOS Say (free)" },
  { id: "fish_audio", label: "Fish Audio" },
  { id: "claude_tts", label: "Claude TTS" },
  { id: "elevenlabs", label: "ElevenLabs" },
  { id: "openai_tts", label: "OpenAI TTS" },
];

const STT_PROVIDERS = [
  { id: "macos_dictation", label: "macOS Dictation (free)" },
  { id: "whisper_local", label: "Whisper (local)" },
  { id: "openai_whisper", label: "OpenAI Whisper" },
  { id: "deepgram", label: "Deepgram" },
];

function ShimmerCard() {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-5">
        <div className="h-5 w-28 rounded bg-border-subtle loading-shimmer" />
        <div className="h-8 w-16 rounded-lg bg-border-subtle loading-shimmer" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <div className="h-3.5 w-20 rounded bg-border-subtle loading-shimmer" />
          <div className="h-10 w-full rounded-lg bg-border-subtle loading-shimmer" />
        </div>
        <div className="space-y-2">
          <div className="h-3.5 w-24 rounded bg-border-subtle loading-shimmer" />
          <div className="h-10 w-full rounded-lg bg-border-subtle loading-shimmer" />
        </div>
      </div>
    </div>
  );
}

function SaveButton({
  dirty,
  onClick,
}: {
  dirty: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={!dirty}
      className={`
        text-sm font-semibold font-body px-4 py-1.5 rounded-lg transition-all duration-200
        ${
          dirty
            ? "bg-accent hover:bg-accent/80 text-white shadow-[0_0_12px_rgba(192,145,90,0.2)]"
            : "bg-elevated text-text-muted border border-border-subtle cursor-not-allowed"
        }
      `}
    >
      Save
    </button>
  );
}

function formatLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Settings() {
  const { toast } = useToast();
  const { refresh: refreshPersonality } = usePersonality();
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [notifications, setNotifications] = useState<Record<
    string,
    unknown
  > | null>(null);
  const [dirty, setDirty] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    try {
      const [s, n] = await Promise.all([
        fetchSettings(),
        fetchNotifications(),
      ]);
      setSettings(s as SettingsData);
      setNotifications(n);
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
      toast(`${formatLabel(section)} saved`);
    } catch {
      toast(`Failed to save ${section}`, "error");
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

  const personality = settings?.personality;
  const voice = settings?.voice;
  const communication = settings?.communication;

  /* ------------------------------------------------------------------ */
  /*  Loading state                                                      */
  /* ------------------------------------------------------------------ */
  if (!settings) {
    return (
      <div>
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-display font-semibold text-text-primary tracking-tight">
            Settings
          </h1>
        </div>
        <div className="space-y-6">
          <ShimmerCard />
          <ShimmerCard />
          <ShimmerCard />
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Render                                                              */
  /* ------------------------------------------------------------------ */
  return (
    <div>
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-display font-semibold text-text-primary tracking-tight">
          Settings
        </h1>
        <button onClick={handleExport} className="btn-secondary">
          Export All Data
        </button>
      </div>

      <div className="space-y-6">
        {/* ── Personality ─────────────────────────────────────────── */}
        {personality && (
          <Card>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-semibold text-lg text-text-primary">
                Personality
              </h2>
              <SaveButton
                dirty={dirty.has("personality")}
                onClick={async () => {
                  await handleSave("personality");
                  refreshPersonality();
                }}
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-body text-text-secondary mb-1.5">
                  Your Name
                </label>
                <input
                  type="text"
                  value={String(personality.user_display_name ?? "")}
                  onChange={(e) =>
                    handleChange(
                      "personality",
                      "user_display_name",
                      e.target.value,
                    )
                  }
                  placeholder="Sir"
                  className="input-base w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-body text-text-secondary mb-1.5">
                  Assistant Name
                </label>
                <input
                  type="text"
                  value={String(personality.assistant_name ?? "")}
                  onChange={(e) =>
                    handleChange(
                      "personality",
                      "assistant_name",
                      e.target.value,
                    )
                  }
                  placeholder="JARVIS"
                  className="input-base w-full"
                />
              </div>
            </div>
          </Card>
        )}

        {/* ── Voice ───────────────────────────────────────────────── */}
        {voice && (
          <Card>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-semibold text-lg text-text-primary">
                Voice
              </h2>
              <SaveButton
                dirty={dirty.has("voice")}
                onClick={() => handleSave("voice")}
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-body text-text-secondary mb-1.5">
                  Text-to-Speech
                </label>
                <select
                  value={String(
                    (voice as Record<string, unknown>).tts_provider ??
                      "macos_say",
                  )}
                  onChange={(e) =>
                    handleChange("voice", "tts_provider", e.target.value)
                  }
                  className="input-base w-full appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%236b7194%22%20d%3D%22M2%204l4%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_12px_center] bg-no-repeat pr-8"
                >
                  {TTS_PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-body text-text-secondary mb-1.5">
                  Speech-to-Text
                </label>
                <select
                  value={String(
                    (voice as Record<string, unknown>).stt_provider ??
                      "macos_dictation",
                  )}
                  onChange={(e) =>
                    handleChange("voice", "stt_provider", e.target.value)
                  }
                  className="input-base w-full appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2212%22%20height%3D%2212%22%20viewBox%3D%220%200%2012%2012%22%3E%3Cpath%20fill%3D%22%236b7194%22%20d%3D%22M2%204l4%204%204-4%22%2F%3E%3C%2Fsvg%3E')] bg-[length:12px] bg-[right_12px_center] bg-no-repeat pr-8"
                >
                  {STT_PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Card>
        )}

        {/* ── Channels (read-only) ────────────────────────────────── */}
        {communication && (
          <Card>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-semibold text-lg text-text-primary">
                Channels
              </h2>
              <span className="text-xs font-body text-text-muted">
                Re-run setup to change channels
              </span>
            </div>
            <div className="space-y-1">
              {Object.entries(communication).map(([key, value]) => {
                if (typeof value !== "object" || value === null) return null;
                const label = formatLabel(key);
                return (
                  <div
                    key={key}
                    className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-surface/60 transition-colors border-b border-border-subtle last:border-0"
                  >
                    <span className="text-sm font-body text-text-primary">
                      {label}
                    </span>
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium font-body text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Configured
                    </span>
                  </div>
                );
              })}
              {Object.entries(communication).filter(
                ([, v]) => typeof v === "object" && v !== null,
              ).length === 0 && (
                <p className="text-sm text-text-muted font-body py-2">
                  No channels configured yet.
                </p>
              )}
            </div>
          </Card>
        )}

        {/* ── Generic sections (Behavior / Briefing / Privacy) ──── */}
        {GENERIC_SECTIONS.map((section) => {
          const data = settings[section];
          if (!data) return null;

          const entries = Object.entries(data).filter(
            ([, value]) => !(typeof value === "object" && value !== null),
          );
          if (entries.length === 0) return null;

          return (
            <Card key={section}>
              <div className="flex items-center justify-between mb-5">
                <h2 className="font-display font-semibold text-lg text-text-primary">
                  {formatLabel(section)}
                </h2>
                <SaveButton
                  dirty={dirty.has(section)}
                  onClick={() => handleSave(section)}
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-4">
                {entries.map(([key, value]) => (
                  <div key={key}>
                    <label className="block text-sm font-body text-text-secondary mb-1.5">
                      {formatLabel(key)}
                    </label>
                    {typeof value === "boolean" ? (
                      <div className="pt-1">
                        <Toggle
                          checked={value}
                          onChange={(v) => handleChange(section, key, v)}
                        />
                      </div>
                    ) : typeof value === "number" ? (
                      <input
                        type="number"
                        value={value}
                        onChange={(e) =>
                          handleChange(
                            section,
                            key,
                            e.target.value === ""
                              ? ""
                              : Number(e.target.value),
                          )
                        }
                        className="input-base w-full"
                      />
                    ) : (
                      <input
                        type="text"
                        value={String(value ?? "")}
                        onChange={(e) =>
                          handleChange(section, key, e.target.value)
                        }
                        className="input-base w-full"
                      />
                    )}
                  </div>
                ))}
              </div>
            </Card>
          );
        })}

        {/* ── Notifications (read-only display) ───────────────────── */}
        {notifications && (
          <Card>
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-semibold text-lg text-text-primary">
                Notifications
              </h2>
            </div>
            <pre className="text-xs font-mono bg-primary/60 text-text-secondary p-4 rounded-lg overflow-auto max-h-56 border border-border-subtle leading-relaxed">
              {JSON.stringify(notifications, null, 2)}
            </pre>
          </Card>
        )}
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { useToast } from "../components/Toast";
import { startSetup, submitStep, skipStep } from "../api/setup";
import { register, login } from "../api/auth";
import { useAuth } from "../stores/auth";

const CHANNELS = [
  { id: "imessage", label: "iMessage" },
  { id: "telegram", label: "Telegram" },
  { id: "discord", label: "Discord" },
  { id: "slack", label: "Slack" },
  { id: "email", label: "Email" },
  { id: "macos_notifications", label: "macOS Notifications" },
];

const SERVICES = [
  { id: "apple", label: "Apple (iCloud, Calendar, Reminders)" },
  { id: "google", label: "Google (Gmail, Calendar, Drive)" },
  { id: "github", label: "GitHub" },
  { id: "linear", label: "Linear" },
  { id: "notion", label: "Notion" },
];

const SCOUT_SOURCES = [
  { id: "hackernews", label: "Hacker News" },
  { id: "github_trending", label: "GitHub Trending" },
  { id: "producthunt", label: "Product Hunt" },
  { id: "arxiv", label: "arXiv Papers" },
];

const TTS_PROVIDERS = [
  { id: "macos_say", label: "macOS Say (free, built-in)" },
  { id: "fish_audio", label: "Fish Audio" },
  { id: "claude_tts", label: "Claude TTS" },
  { id: "elevenlabs", label: "ElevenLabs" },
  { id: "openai_tts", label: "OpenAI TTS" },
];

const STT_PROVIDERS = [
  { id: "macos_dictation", label: "macOS Dictation (free, built-in)" },
  { id: "whisper_local", label: "Whisper (local)" },
  { id: "openai_whisper", label: "OpenAI Whisper" },
  { id: "deepgram", label: "Deepgram" },
];

interface StepMeta {
  title: string;
  description: string;
  required: boolean;
}

const STEP_META: Record<number, StepMeta> = {
  1: { title: "Welcome", description: "Welcome to JARVIS — your personal AI assistant. Let's get you set up.", required: true },
  2: { title: "Personalization", description: "What should JARVIS call you?", required: false },
  3: { title: "Communication", description: "How should JARVIS reach you? Add your channels and credentials.", required: false },
  4: { title: "Claude Desktop", description: "Registering JARVIS as an MCP server in Claude Desktop.", required: true },
  5: { title: "Contacts", description: "Auto-importing your macOS contacts for easy messaging.", required: false },
  6: { title: "Services", description: "Which service ecosystems do you use?", required: false },
  7: { title: "Scout Sources", description: "Where should Scout look for discoveries?", required: false },
  8: { title: "GitHub Auth", description: "Checking GitHub CLI authentication.", required: false },
  9: { title: "Obsidian Vault", description: "Link your Obsidian vault for notes and knowledge.", required: false },
  10: { title: "Voice Setup", description: "Choose your text-to-speech and speech-to-text providers.", required: false },
  11: { title: "First Scan", description: "Running your first Scout discovery scan.", required: false },
  12: { title: "Create Account", description: "Set up your Mission Control login to finish.", required: false },
};

export function Setup() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [step, setStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(12);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [stepResult, setStepResult] = useState<Record<string, unknown> | null>(null);
  const [nicknames, setNicknames] = useState<{ name: string; contact: string }[]>([{ name: "", contact: "" }]);

  useEffect(() => {
    startSetup()
      .then((progress) => {
        setStep(progress.current_step);
        setTotalSteps(progress.total_steps);
      })
      .catch(() => {});
  }, []);

  async function handleNext() {
    if (step === 12) {
      const username = config.username as string;
      const password = config.password as string;
      if (!username || !password) {
        toast("Username and password are required", "error");
        return;
      }
      if ((password as string).length < 4) {
        toast("Password must be at least 4 characters", "error");
        return;
      }
    }

    setLoading(true);
    try {
      let stepConfig = { ...config };
      if (step === 5) {
        const nicknameMap: Record<string, string> = {};
        for (const n of nicknames) {
          if (n.name.trim() && n.contact.trim()) {
            nicknameMap[n.name.trim()] = n.contact.trim();
          }
        }
        stepConfig = { nicknames: nicknameMap };
      }

      const result = await submitStep(step, stepConfig);
      setStepResult(result);

      if (result.complete) {
        if (config.username && config.password) {
          try {
            await register(config.username as string, config.password as string);
          } catch {
            // User may already exist
          }
          await login(config.username as string, config.password as string);
          await refresh();
        }
        toast("Setup complete — welcome to JARVIS");
        navigate("/");
        return;
      }
      setStep((result.current_step as number) ?? step + 1);
      setConfig({});
      setStepResult(null);
      setNicknames([{ name: "", contact: "" }]);
    } catch {
      toast("Step failed", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleSkip() {
    try {
      const result = await skipStep(step);
      setStep((result.current_step as number) ?? step + 1);
      setConfig({});
      setStepResult(null);
      setNicknames([{ name: "", contact: "" }]);
    } catch {
      toast("Cannot skip this step", "error");
    }
  }

  function setField(key: string, value: unknown) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  function toggleInArray(key: string, item: string) {
    setConfig((prev) => {
      const arr = (prev[key] as string[]) || [];
      const next = arr.includes(item)
        ? arr.filter((i) => i !== item)
        : [...arr, item];
      return { ...prev, [key]: next };
    });
  }

  const meta = STEP_META[step] || { title: `Step ${step}`, description: "", required: false };
  const pct = totalSteps > 0 ? Math.round((step / totalSteps) * 100) : 0;

  const needsApiKey = (provider: string) =>
    ["fish_audio", "elevenlabs", "openai_tts", "openai_whisper", "deepgram"].includes(provider);

  function renderStepForm() {
    switch (step) {
      case 1:
        return (
          <div className="text-center py-4">
            <div className="w-16 h-16 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-4">
              <div className="w-6 h-6 rounded-full bg-accent" />
            </div>
            <p className="text-text-primary mb-2">
              I work with your Claude subscription to keep your Mac organised, your projects watched, and your mornings briefed.
            </p>
            <p className="text-text-secondary text-sm">
              This wizard will walk you through connecting services, setting preferences, and creating your account.
            </p>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">Your name</label>
              <input
                type="text"
                placeholder="Sir"
                value={(config.user_name as string) ?? ""}
                onChange={(e) => setField("user_name", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Assistant name</label>
              <input
                type="text"
                placeholder="JARVIS"
                value={(config.assistant_name as string) ?? ""}
                onChange={(e) => setField("assistant_name", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
          </div>
        );

      case 3: {
        const selectedChannels = ((config.channels as string[]) || []);
        const imessageEnabled = selectedChannels.includes("imessage");
        const telegramEnabled = selectedChannels.includes("telegram");
        const discordEnabled = selectedChannels.includes("discord");
        const slackEnabled = selectedChannels.includes("slack");
        const emailEnabled = selectedChannels.includes("email");
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-2">Enable channels</label>
              <div className="space-y-2">
                {CHANNELS.map((ch) => {
                  const enabled = selectedChannels.includes(ch.id);
                  return (
                    <label key={ch.id} className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={() => toggleInArray("channels", ch.id)}
                        className="accent-accent w-4 h-4"
                      />
                      <span className="text-text-primary text-sm">{ch.label}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            {imessageEnabled && (
              <div className="bg-card/50 border border-border-default rounded-lg p-3 space-y-2">
                <p className="text-xs font-medium text-text-secondary uppercase">iMessage</p>
                <input
                  type="text"
                  placeholder="+1 555-123-4567 or you@icloud.com"
                  value={(config.imessage_target as string) ?? ""}
                  onChange={(e) => setField("imessage_target", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
              </div>
            )}

            {telegramEnabled && (
              <div className="bg-card/50 border border-border-default rounded-lg p-3 space-y-2">
                <p className="text-xs font-medium text-text-secondary uppercase">Telegram Bot</p>
                <input
                  type="text"
                  placeholder="Bot token (from @BotFather)"
                  value={(config.telegram_bot_token as string) ?? ""}
                  onChange={(e) => setField("telegram_bot_token", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Chat ID"
                  value={(config.telegram_chat_id as string) ?? ""}
                  onChange={(e) => setField("telegram_chat_id", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
                <p className="text-xs text-text-secondary">Create a bot via @BotFather on Telegram, then message it and use the API to get your chat ID.</p>
              </div>
            )}

            {discordEnabled && (
              <div className="bg-card/50 border border-border-default rounded-lg p-3 space-y-2">
                <p className="text-xs font-medium text-text-secondary uppercase">Discord Bot</p>
                <input
                  type="text"
                  placeholder="Bot token"
                  value={(config.discord_bot_token as string) ?? ""}
                  onChange={(e) => setField("discord_bot_token", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Channel ID"
                  value={(config.discord_channel_id as string) ?? ""}
                  onChange={(e) => setField("discord_channel_id", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
              </div>
            )}

            {slackEnabled && (
              <div className="bg-card/50 border border-border-default rounded-lg p-3 space-y-2">
                <p className="text-xs font-medium text-text-secondary uppercase">Slack Bot</p>
                <input
                  type="text"
                  placeholder="Bot token (xoxb-...)"
                  value={(config.slack_bot_token as string) ?? ""}
                  onChange={(e) => setField("slack_bot_token", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Channel ID"
                  value={(config.slack_channel_id as string) ?? ""}
                  onChange={(e) => setField("slack_channel_id", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
              </div>
            )}

            {emailEnabled && (
              <div className="bg-card/50 border border-border-default rounded-lg p-3 space-y-2">
                <p className="text-xs font-medium text-text-secondary uppercase">Email</p>
                <input
                  type="text"
                  placeholder="SMTP host (e.g. smtp.gmail.com)"
                  value={(config.email_smtp_host as string) ?? ""}
                  onChange={(e) => setField("email_smtp_host", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Username"
                    value={(config.email_username as string) ?? ""}
                    onChange={(e) => setField("email_username", e.target.value)}
                    className="flex-1 bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={(config.email_password as string) ?? ""}
                    onChange={(e) => setField("email_password", e.target.value)}
                    className="flex-1 bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                  />
                </div>
                <input
                  type="text"
                  placeholder="IMAP host (e.g. imap.gmail.com)"
                  value={(config.email_imap_host as string) ?? ""}
                  onChange={(e) => setField("email_imap_host", e.target.value)}
                  className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
              </div>
            )}

            <div>
              <label className="block text-sm text-text-secondary mb-1">Primary channel</label>
              <select
                value={(config.primary as string) ?? ""}
                onChange={(e) => setField("primary", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
              >
                <option value="">Select primary channel</option>
                {CHANNELS.map((ch) => (
                  <option key={ch.id} value={ch.id}>{ch.label}</option>
                ))}
              </select>
            </div>
          </div>
        );
      }

      case 4:
        return (
          <div className="text-center py-4">
            <div className="w-12 h-12 rounded-full bg-success/20 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-text-primary font-medium">Register JARVIS in Claude Desktop</p>
            <p className="text-text-secondary text-sm mt-1">
              JARVIS will be added as an MCP server so Claude can use its tools.
            </p>
          </div>
        );

      case 5:
        return (
          <div className="text-center py-4">
            <div className="w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <p className="text-text-primary font-medium">Auto-Importing Contacts</p>
            <p className="text-text-secondary text-sm mt-1">
              Scanning your macOS Contacts so you can say "text mom" instead of typing a full name.
            </p>
          </div>
        );

      case 6:
        return (
          <div className="space-y-2">
            {SERVICES.map((svc) => {
              const enabled = ((config.services as string[]) || []).includes(svc.id);
              return (
                <label key={svc.id} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggleInArray("services", svc.id)}
                    className="accent-accent w-4 h-4"
                  />
                  <span className="text-text-primary text-sm">{svc.label}</span>
                </label>
              );
            })}
          </div>
        );

      case 7:
        return (
          <div className="space-y-2">
            {SCOUT_SOURCES.map((src) => {
              const enabled = ((config.sources as string[]) || []).includes(src.id);
              return (
                <label key={src.id} className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggleInArray("sources", src.id)}
                    className="accent-accent w-4 h-4"
                  />
                  <span className="text-text-primary text-sm">{src.label}</span>
                </label>
              );
            })}
          </div>
        );

      case 8:
        return (
          <div className="text-center py-4">
            <div className="w-12 h-12 rounded-full bg-success/20 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-text-primary font-medium">GitHub CLI</p>
            <p className="text-text-secondary text-sm mt-1">Checking authentication status...</p>
          </div>
        );

      case 9:
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">Obsidian vault path</label>
              <input
                type="text"
                placeholder="~/Documents/Obsidian/MyVault"
                value={(config.vault_path as string) ?? ""}
                onChange={(e) => setField("vault_path", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
              />
              <p className="text-xs text-text-secondary mt-1">
                Point to the folder that contains your .obsidian directory. Leave empty to skip.
              </p>
            </div>
          </div>
        );

      case 10: {
        const ttsProvider = (config.tts_provider as string) ?? "macos_say";
        const sttProvider = (config.stt_provider as string) ?? "macos_dictation";
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">Text-to-Speech</label>
              <select
                value={ttsProvider}
                onChange={(e) => setField("tts_provider", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
              >
                {TTS_PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
              {needsApiKey(ttsProvider) && (
                <input
                  type="password"
                  placeholder="API key"
                  value={(config.tts_api_key as string) ?? ""}
                  onChange={(e) => setField("tts_api_key", e.target.value)}
                  className="w-full mt-2 bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
              )}
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Speech-to-Text</label>
              <select
                value={sttProvider}
                onChange={(e) => setField("stt_provider", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
              >
                {STT_PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>{p.label}</option>
                ))}
              </select>
              {needsApiKey(sttProvider) && (
                <input
                  type="password"
                  placeholder="API key"
                  value={(config.stt_api_key as string) ?? ""}
                  onChange={(e) => setField("stt_api_key", e.target.value)}
                  className="w-full mt-2 bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary text-sm focus:border-accent focus:outline-none"
                />
              )}
            </div>
          </div>
        );
      }

      case 11:
        return (
          <div className="text-center py-4">
            <div className="w-12 h-12 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-accent animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <p className="text-text-primary font-medium">Ready to Scan</p>
            <p className="text-text-secondary text-sm mt-1">
              Click Next to run your first Scout discovery and find tools, news, and repos relevant to you.
            </p>
          </div>
        );

      case 12:
        return (
          <div className="space-y-4">
            <p className="text-text-secondary text-sm">
              Create a Mission Control account to access the dashboard.
            </p>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Username</label>
              <input
                type="text"
                value={(config.username as string) ?? ""}
                onChange={(e) => setField("username", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">Password</label>
              <input
                type="password"
                value={(config.password as string) ?? ""}
                onChange={(e) => setField("password", e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
          </div>
        );

      default:
        return null;
    }
  }

  const isAutoStep = [4, 5, 8].includes(step);

  return (
    <div className="min-h-screen bg-primary flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-2.5 h-2.5 rounded-full bg-accent" />
          <h1 className="text-xl font-semibold text-text-primary">
            Jarvis Setup
          </h1>
        </div>

        <div className="mb-6">
          <div className="flex justify-between text-xs text-text-secondary mb-1">
            <span>Step {step} of {totalSteps}</span>
            <span>{pct}%</span>
          </div>
          <div className="h-1.5 bg-card rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        <Card>
          <h2 className="text-lg font-semibold text-text-primary mb-1">
            {meta.title}
          </h2>
          <p className="text-text-secondary text-sm mb-6">
            {meta.description}
          </p>

          <div className="mb-6">{renderStepForm()}</div>

          {typeof stepResult?.message === "string" && (
            <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2 mb-4">
              <p className="text-sm text-accent">{stepResult.message}</p>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleNext}
              disabled={loading}
              className="flex-1 bg-accent hover:bg-accent-hover text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {loading
                ? step === 11
                  ? "Scanning..."
                  : "..."
                : step === totalSteps
                  ? "Finish"
                  : isAutoStep
                    ? "Continue"
                    : "Next"}
            </button>
            {!meta.required && !isAutoStep && step !== 12 && (
              <button
                onClick={handleSkip}
                className="bg-card border border-border-default text-text-secondary px-4 py-2.5 rounded-lg hover:text-text-primary transition-colors"
              >
                Skip
              </button>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

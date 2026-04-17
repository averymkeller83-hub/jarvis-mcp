import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { useToast } from "../components/Toast";
import { usePersonality } from "../stores/personality";
import { startSetup, submitStep, skipStep, verifyChannel, sendTestMessage } from "../api/setup";

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

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

/* ------------------------------------------------------------------ */
/*  Step metadata                                                      */
/* ------------------------------------------------------------------ */

interface StepMeta {
  title: string;
  description: string;
  required: boolean;
}

function getStepMeta(name: string): Record<number, StepMeta> {
  return {
    1: { title: "Welcome", description: `Welcome to ${name} — your personal AI assistant. Let's get you set up.`, required: true },
    2: { title: "Personalization", description: `What should ${name} call you?`, required: false },
    3: { title: "Communication", description: `How should ${name} reach you? Add your channels and credentials.`, required: false },
    4: { title: "Claude Desktop", description: `Registering ${name} as an MCP server in Claude Desktop.`, required: true },
    5: { title: "Contacts", description: "Auto-importing your macOS contacts for easy messaging.", required: false },
    6: { title: "Services", description: "Which service ecosystems do you use?", required: false },
    7: { title: "Scout Sources", description: "Where should Scout look for discoveries?", required: false },
    8: { title: "GitHub Auth", description: "Checking GitHub CLI authentication.", required: false },
    9: { title: "Obsidian Vault", description: "Link your Obsidian vault for notes and knowledge.", required: false },
    10: { title: "Voice Setup", description: "Choose your text-to-speech and speech-to-text providers.", required: false },
    11: { title: "First Scan", description: "Running your first Scout discovery scan.", required: false },
    12: { title: "Setup Complete", description: `${name} is ready. Let's go.`, required: false },
  };
}

/* ------------------------------------------------------------------ */
/*  Logo                                                               */
/* ------------------------------------------------------------------ */

function JarvisMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.2" className="text-border-default" />
      <circle cx="16" cy="16" r="8" stroke="currentColor" strokeWidth="1" className="text-accent/60" />
      <circle cx="16" cy="16" r="3" fill="currentColor" className="text-accent" />
      <line x1="16" y1="2" x2="16" y2="8" stroke="currentColor" strokeWidth="0.8" className="text-border-default" />
      <line x1="16" y1="24" x2="16" y2="30" stroke="currentColor" strokeWidth="0.8" className="text-border-default" />
      <line x1="2" y1="16" x2="8" y2="16" stroke="currentColor" strokeWidth="0.8" className="text-border-default" />
      <line x1="24" y1="16" x2="30" y2="16" stroke="currentColor" strokeWidth="0.8" className="text-border-default" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export function Setup() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { refresh: refreshPersonality } = usePersonality();
  const [step, setStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(12);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(false);
  const [stepResult, setStepResult] = useState<Record<string, unknown> | null>(null);
  const [nicknames, setNicknames] = useState<{ name: string; contact: string }[]>([{ name: "", contact: "" }]);
  const [aName, setAName] = useState("JARVIS");
  const [verified, setVerified] = useState<Record<string, { ok: boolean; message: string }>>({});
  const [verifying, setVerifying] = useState<Record<string, boolean>>({});
  const [stepConfigs, setStepConfigs] = useState<Record<number, Record<string, unknown>>>({});
  const [testSent, setTestSent] = useState<Record<string, { ok: boolean; message: string }>>({});
  const [testSending, setTestSending] = useState<Record<string, boolean>>({});

  useEffect(() => {
    startSetup()
      .then((progress) => {
        setStep(progress.current_step);
        setTotalSteps(progress.total_steps);
      })
      .catch(() => {});
  }, []);

  async function handleNext() {
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

      setStepConfigs((prev) => ({ ...prev, [step]: { ...stepConfig } }));

      const result = await submitStep(step, stepConfig);
      setStepResult(result);

      if (step === 2) {
        const chosen = (config.assistant_name as string)?.trim();
        if (chosen) setAName(chosen);
      }

      if (result.complete) {
        await refreshPersonality();
        toast(`Setup complete — welcome to ${aName}`);
        navigate("/login");
        return;
      }
      const nextStep = (result.current_step as number) ?? step + 1;
      setStep(nextStep);
      setConfig(stepConfigs[nextStep] || {});
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
      setStepConfigs((prev) => ({ ...prev, [step]: { ...config } }));
      const result = await skipStep(step);
      const nextStep = (result.current_step as number) ?? step + 1;
      setStep(nextStep);
      setConfig(stepConfigs[nextStep] || {});
      setStepResult(null);
      setNicknames([{ name: "", contact: "" }]);
    } catch {
      toast("Cannot skip this step", "error");
    }
  }

  function handleBack() {
    if (step <= 1) return;
    setStepConfigs((prev) => ({ ...prev, [step]: { ...config } }));
    const prevStep = step - 1;
    setStep(prevStep);
    setConfig(stepConfigs[prevStep] || {});
    setStepResult(null);
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

  async function handleVerify(channel: string, creds: Record<string, string>) {
    setVerifying((v) => ({ ...v, [channel]: true }));
    try {
      const result = await verifyChannel(channel, creds);
      if (result.ok) {
        const detail =
          result.bot_name ? `Connected to @${result.bot_name}` :
          result.username ? `Authenticated as ${result.username}` :
          result.target ? `Valid ${result.type}: ${result.target}` :
          "Verified";
        setVerified((v) => ({ ...v, [channel]: { ok: true, message: detail } }));
      } else {
        setVerified((v) => ({ ...v, [channel]: { ok: false, message: result.error ?? "Verification failed" } }));
      }
    } catch {
      setVerified((v) => ({ ...v, [channel]: { ok: false, message: "Could not reach server" } }));
    } finally {
      setVerifying((v) => ({ ...v, [channel]: false }));
    }
  }

  async function handleTestMessage(channel: string, creds: Record<string, string>) {
    setTestSending((v) => ({ ...v, [channel]: true }));
    try {
      const result = await sendTestMessage(channel, creds);
      setTestSent((v) => ({
        ...v,
        [channel]: {
          ok: result.ok,
          message: result.ok ? "Test message sent!" : result.error ?? "Send failed",
        },
      }));
    } catch {
      setTestSent((v) => ({ ...v, [channel]: { ok: false, message: "Could not reach server" } }));
    } finally {
      setTestSending((v) => ({ ...v, [channel]: false }));
    }
  }

  const stepMeta = getStepMeta(aName);
  const meta = stepMeta[step] || { title: `Step ${step}`, description: "", required: false };
  const pct = totalSteps > 0 ? Math.round((step / totalSteps) * 100) : 0;

  const needsApiKey = (provider: string) =>
    ["fish_audio", "elevenlabs", "openai_tts", "openai_whisper", "deepgram"].includes(provider);

  /* ---------------------------------------------------------------- */
  /*  Sub-components                                                   */
  /* ---------------------------------------------------------------- */

  function VerifyBadge({ channel }: { channel: string }) {
    const v = verified[channel];
    const busy = verifying[channel];
    if (busy) return <span className="text-xs text-text-secondary animate-pulse font-mono">Verifying...</span>;
    if (!v) return null;
    if (v.ok) return (
      <span className="inline-flex items-center gap-1.5 text-xs text-success font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-success" />
        {v.message}
      </span>
    );
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-danger font-mono">
        <span className="w-1.5 h-1.5 rounded-full bg-danger" />
        {v.message}
      </span>
    );
  }

  function TestMessageButton({ channel, creds }: { channel: string; creds: Record<string, string> }) {
    if (!verified[channel]?.ok) return null;
    const sent = testSent[channel];
    const sending = testSending[channel];
    return (
      <div className="mt-2">
        <button
          type="button"
          onClick={() => handleTestMessage(channel, creds)}
          disabled={sending}
          className="w-full bg-success-muted border border-success/20 text-success text-xs font-semibold py-2 rounded-lg hover:bg-success/20 hover:border-success/30 transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {sending ? "Sending..." : "Send Test Message"}
        </button>
        {sent && (
          <span className={`text-xs mt-1.5 block font-mono ${sent.ok ? "text-success" : "text-danger"}`}>
            {sent.message}
          </span>
        )}
      </div>
    );
  }

  /* ---------------------------------------------------------------- */
  /*  Channel config card (shared layout for step 3 channel sections) */
  /* ---------------------------------------------------------------- */

  function ChannelSection({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
    return (
      <div className="glass rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="section-title">{label}</p>
          <VerifyBadge channel={id} />
        </div>
        {children}
      </div>
    );
  }

  /* ---------------------------------------------------------------- */
  /*  Step form renderer                                               */
  /* ---------------------------------------------------------------- */

  function renderStepForm() {
    switch (step) {
      case 1:
        return (
          <div className="text-center py-6">
            <div className="flex justify-center mb-6">
              <div className="animate-pulse-glow rounded-full p-2">
                <JarvisMark size={64} />
              </div>
            </div>
            <p className="text-text-primary font-body text-base leading-relaxed mb-3">
              I work with your Claude subscription to keep your Mac organised, your projects watched, and your mornings briefed.
            </p>
            <p className="text-text-secondary text-sm font-body leading-relaxed">
              This wizard will walk you through connecting services, setting preferences, and creating your account.
            </p>
          </div>
        );

      case 2:
        return (
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2 font-body">
                Your name
              </label>
              <input
                type="text"
                placeholder="Sir"
                value={(config.user_name as string) ?? ""}
                onChange={(e) => setField("user_name", e.target.value)}
                className="input-base"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2 font-body">
                Assistant name
              </label>
              <input
                type="text"
                placeholder="JARVIS"
                value={(config.assistant_name as string) ?? ""}
                onChange={(e) => setField("assistant_name", e.target.value)}
                className="input-base"
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
          <div className="space-y-5">
            {/* Channel toggles */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-3 font-body">
                Enable channels
              </label>
              <div className="space-y-2.5">
                {CHANNELS.map((ch) => {
                  const enabled = selectedChannels.includes(ch.id);
                  return (
                    <label key={ch.id} className="flex items-center gap-3 cursor-pointer group">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={() => toggleInArray("channels", ch.id)}
                        className="accent-accent w-4 h-4 rounded"
                      />
                      <span className="text-text-primary text-sm font-body group-hover:text-accent transition-colors duration-200">
                        {ch.label}
                      </span>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* iMessage config */}
            {imessageEnabled && (
              <ChannelSection id="imessage" label="iMessage">
                <input
                  type="text"
                  placeholder="+1 555-123-4567 or you@icloud.com"
                  value={(config.imessage_target as string) ?? ""}
                  onChange={(e) => { setField("imessage_target", e.target.value); setVerified((v) => { const n = { ...v }; delete n.imessage; return n; }); }}
                  className="input-base"
                />
                <button
                  type="button"
                  onClick={() => handleVerify("imessage", { target: (config.imessage_target as string) ?? "" })}
                  disabled={verifying.imessage}
                  className="btn-secondary w-full text-xs"
                >
                  Verify Format
                </button>
                <TestMessageButton channel="imessage" creds={{ target: (config.imessage_target as string) ?? "" }} />
              </ChannelSection>
            )}

            {/* Telegram config */}
            {telegramEnabled && (
              <ChannelSection id="telegram" label="Telegram Bot">
                <input
                  type="text"
                  placeholder="Bot token (from @BotFather)"
                  value={(config.telegram_bot_token as string) ?? ""}
                  onChange={(e) => { setField("telegram_bot_token", e.target.value); setVerified((v) => { const n = { ...v }; delete n.telegram; return n; }); }}
                  className="input-base"
                />
                <input
                  type="text"
                  placeholder="Chat ID"
                  value={(config.telegram_chat_id as string) ?? ""}
                  onChange={(e) => { setField("telegram_chat_id", e.target.value); setVerified((v) => { const n = { ...v }; delete n.telegram; return n; }); }}
                  className="input-base"
                />
                <button
                  type="button"
                  onClick={() => handleVerify("telegram", { bot_token: (config.telegram_bot_token as string) ?? "", chat_id: (config.telegram_chat_id as string) ?? "" })}
                  disabled={verifying.telegram}
                  className="btn-secondary w-full text-xs"
                >
                  Verify Connection
                </button>
                <TestMessageButton channel="telegram" creds={{ bot_token: (config.telegram_bot_token as string) ?? "", chat_id: (config.telegram_chat_id as string) ?? "" }} />
                <p className="text-xs text-text-muted font-body">
                  Create a bot via @BotFather on Telegram, then message it and use the API to get your chat ID.
                </p>
              </ChannelSection>
            )}

            {/* Discord config */}
            {discordEnabled && (
              <ChannelSection id="discord" label="Discord Bot">
                <input
                  type="text"
                  placeholder="Bot token"
                  value={(config.discord_bot_token as string) ?? ""}
                  onChange={(e) => { setField("discord_bot_token", e.target.value); setVerified((v) => { const n = { ...v }; delete n.discord; return n; }); }}
                  className="input-base"
                />
                <input
                  type="text"
                  placeholder="Channel ID"
                  value={(config.discord_channel_id as string) ?? ""}
                  onChange={(e) => { setField("discord_channel_id", e.target.value); setVerified((v) => { const n = { ...v }; delete n.discord; return n; }); }}
                  className="input-base"
                />
                <button
                  type="button"
                  onClick={() => handleVerify("discord", { bot_token: (config.discord_bot_token as string) ?? "", channel_id: (config.discord_channel_id as string) ?? "" })}
                  disabled={verifying.discord}
                  className="btn-secondary w-full text-xs"
                >
                  Verify Connection
                </button>
                <TestMessageButton channel="discord" creds={{ bot_token: (config.discord_bot_token as string) ?? "", channel_id: (config.discord_channel_id as string) ?? "" }} />
              </ChannelSection>
            )}

            {/* Slack config */}
            {slackEnabled && (
              <ChannelSection id="slack" label="Slack Bot">
                <input
                  type="text"
                  placeholder="Bot token (xoxb-...)"
                  value={(config.slack_bot_token as string) ?? ""}
                  onChange={(e) => { setField("slack_bot_token", e.target.value); setVerified((v) => { const n = { ...v }; delete n.slack; return n; }); }}
                  className="input-base"
                />
                <input
                  type="text"
                  placeholder="Channel ID"
                  value={(config.slack_channel_id as string) ?? ""}
                  onChange={(e) => { setField("slack_channel_id", e.target.value); setVerified((v) => { const n = { ...v }; delete n.slack; return n; }); }}
                  className="input-base"
                />
                <button
                  type="button"
                  onClick={() => handleVerify("slack", { bot_token: (config.slack_bot_token as string) ?? "", channel_id: (config.slack_channel_id as string) ?? "" })}
                  disabled={verifying.slack}
                  className="btn-secondary w-full text-xs"
                >
                  Verify Connection
                </button>
                <TestMessageButton channel="slack" creds={{ bot_token: (config.slack_bot_token as string) ?? "", channel_id: (config.slack_channel_id as string) ?? "" }} />
              </ChannelSection>
            )}

            {/* Email config */}
            {emailEnabled && (
              <ChannelSection id="email" label="Email">
                <input
                  type="text"
                  placeholder="SMTP host (e.g. smtp.gmail.com)"
                  value={(config.email_smtp_host as string) ?? ""}
                  onChange={(e) => { setField("email_smtp_host", e.target.value); setVerified((v) => { const n = { ...v }; delete n.email; return n; }); }}
                  className="input-base"
                />
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Username"
                    value={(config.email_username as string) ?? ""}
                    onChange={(e) => { setField("email_username", e.target.value); setVerified((v) => { const n = { ...v }; delete n.email; return n; }); }}
                    className="input-base flex-1"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={(config.email_password as string) ?? ""}
                    onChange={(e) => { setField("email_password", e.target.value); setVerified((v) => { const n = { ...v }; delete n.email; return n; }); }}
                    className="input-base flex-1"
                  />
                </div>
                <input
                  type="text"
                  placeholder="IMAP host (e.g. imap.gmail.com)"
                  value={(config.email_imap_host as string) ?? ""}
                  onChange={(e) => setField("email_imap_host", e.target.value)}
                  className="input-base"
                />
                <button
                  type="button"
                  onClick={() => handleVerify("email", { smtp_host: (config.email_smtp_host as string) ?? "", smtp_port: "587", username: (config.email_username as string) ?? "", password: (config.email_password as string) ?? "" })}
                  disabled={verifying.email}
                  className="btn-secondary w-full text-xs"
                >
                  Verify SMTP Login
                </button>
                <TestMessageButton channel="email" creds={{ smtp_host: (config.email_smtp_host as string) ?? "", smtp_port: "587", username: (config.email_username as string) ?? "", password: (config.email_password as string) ?? "" }} />
              </ChannelSection>
            )}

            {/* Primary channel */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2 font-body">
                Primary channel
              </label>
              <select
                value={(config.primary as string) ?? ""}
                onChange={(e) => setField("primary", e.target.value)}
                className="input-base"
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
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-success-muted flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-text-primary font-semibold font-display text-lg">Register {aName} in Claude Desktop</p>
            <p className="text-text-secondary text-sm mt-2 font-body leading-relaxed">
              {aName} will be added as an MCP server so Claude can use its tools.
            </p>
          </div>
        );

      case 5:
        return (
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-accent-muted flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <p className="text-text-primary font-semibold font-display text-lg">Auto-Importing Contacts</p>
            <p className="text-text-secondary text-sm mt-2 font-body leading-relaxed">
              Scanning your macOS Contacts so you can say "text mom" instead of typing a full name.
            </p>
          </div>
        );

      case 6:
        return (
          <div className="space-y-3">
            {SERVICES.map((svc) => {
              const enabled = ((config.services as string[]) || []).includes(svc.id);
              return (
                <label key={svc.id} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggleInArray("services", svc.id)}
                    className="accent-accent w-4 h-4 rounded"
                  />
                  <span className="text-text-primary text-sm font-body group-hover:text-accent transition-colors duration-200">
                    {svc.label}
                  </span>
                </label>
              );
            })}
          </div>
        );

      case 7:
        return (
          <div className="space-y-3">
            {SCOUT_SOURCES.map((src) => {
              const enabled = ((config.sources as string[]) || []).includes(src.id);
              return (
                <label key={src.id} className="flex items-center gap-3 cursor-pointer group">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() => toggleInArray("sources", src.id)}
                    className="accent-accent w-4 h-4 rounded"
                  />
                  <span className="text-text-primary text-sm font-body group-hover:text-accent transition-colors duration-200">
                    {src.label}
                  </span>
                </label>
              );
            })}
          </div>
        );

      case 8:
        return (
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-success-muted flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-text-primary font-semibold font-display text-lg">GitHub CLI</p>
            <p className="text-text-secondary text-sm mt-2 font-body">Checking authentication status...</p>
          </div>
        );

      case 9:
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2 font-body">
                Obsidian vault path
              </label>
              <input
                type="text"
                placeholder="~/Documents/Obsidian/MyVault"
                value={(config.vault_path as string) ?? ""}
                onChange={(e) => setField("vault_path", e.target.value)}
                className="input-base"
              />
              <p className="text-xs text-text-muted mt-2 font-body leading-relaxed">
                Point to the folder that contains your .obsidian directory. Leave empty to skip.
              </p>
            </div>
          </div>
        );

      case 10: {
        const ttsProvider = (config.tts_provider as string) ?? "macos_say";
        const sttProvider = (config.stt_provider as string) ?? "macos_dictation";
        return (
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2 font-body">
                Text-to-Speech
              </label>
              <select
                value={ttsProvider}
                onChange={(e) => setField("tts_provider", e.target.value)}
                className="input-base"
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
                  className="input-base mt-2"
                />
              )}
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-muted mb-2 font-body">
                Speech-to-Text
              </label>
              <select
                value={sttProvider}
                onChange={(e) => setField("stt_provider", e.target.value)}
                className="input-base"
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
                  className="input-base mt-2"
                />
              )}
            </div>
          </div>
        );
      }

      case 11:
        return (
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-accent-muted flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-accent animate-spin-slow" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </div>
            <p className="text-text-primary font-semibold font-display text-lg">Ready to Scan</p>
            <p className="text-text-secondary text-sm mt-2 font-body leading-relaxed">
              Click Next to run your first Scout discovery and find tools, news, and repos relevant to you.
            </p>
          </div>
        );

      case 12: {
        const sc = stepConfigs;
        const userName = (sc[2]?.user_name as string) || "Sir";
        const channels = (sc[3]?.channels as string[]) || [];
        const primary = (sc[3]?.primary as string) || channels[0] || "macos_notifications";
        const services = (sc[6]?.services as string[]) || [];
        const sources = (sc[7]?.sources as string[]) || [];
        const vaultPath = (sc[9]?.vault_path as string) || "";
        const ttsProvider = (sc[10]?.tts_provider as string) || "macos_say";
        const sttProvider = (sc[10]?.stt_provider as string) || "macos_dictation";

        const rows: { label: string; value: string }[] = [
          { label: "Name", value: userName },
          { label: "Assistant", value: aName },
          { label: "Primary channel", value: primary },
        ];
        if (channels.length > 0) rows.push({ label: "Channels", value: channels.join(", ") });
        if (services.length > 0) rows.push({ label: "Services", value: services.join(", ") });
        if (sources.length > 0) rows.push({ label: "Scout sources", value: sources.join(", ") });
        if (vaultPath) rows.push({ label: "Obsidian", value: vaultPath });
        rows.push({ label: "TTS / STT", value: `${ttsProvider} / ${sttProvider}` });

        return (
          <div className="space-y-5">
            {/* Success icon */}
            <div className="flex items-center justify-center">
              <div className="w-14 h-14 rounded-full bg-success-muted flex items-center justify-center animate-pulse-glow">
                <svg className="w-7 h-7 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>

            <p className="text-center text-text-primary font-semibold font-display text-lg">
              Review your configuration
            </p>

            {/* Review card */}
            <div className="glass rounded-lg p-4 space-y-0 divide-y divide-border-subtle">
              {rows.map((row, i) => (
                <div key={i} className="flex justify-between items-baseline py-2.5 first:pt-0 last:pb-0">
                  <span className="text-text-secondary text-xs font-mono uppercase tracking-wider">{row.label}</span>
                  <span className="text-text-primary text-sm font-body text-right max-w-[220px] truncate">{row.value}</span>
                </div>
              ))}
            </div>

            <p className="text-center text-text-muted text-xs font-body">
              {aName} will sign you in through Claude Desktop — no extra account needed.
            </p>
          </div>
        );
      }

      default:
        return null;
    }
  }

  const isAutoStep = [4, 5, 8].includes(step);

  /* ---------------------------------------------------------------- */
  /*  Layout                                                           */
  /* ---------------------------------------------------------------- */

  return (
    <div className="min-h-screen bg-void flex items-center justify-center px-4 py-8">
      {/* Subtle radial glow behind content */}
      <div className="fixed inset-0 pointer-events-none bg-page-gradient" />

      <div className="relative w-full max-w-lg animate-slide-up">
        {/* Logo + Title */}
        <div className="flex flex-col items-center mb-8">
          <div className="mb-3">
            <JarvisMark size={40} />
          </div>
          <h1 className="text-xl font-bold text-text-primary font-display tracking-tight">
            {aName} Setup
          </h1>
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-muted mt-1">
            Configuration Wizard
          </p>
        </div>

        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex justify-between items-baseline text-xs mb-2">
            <span className="text-text-secondary font-body">
              Step <span className="text-text-primary font-semibold">{step}</span> of {totalSteps}
            </span>
            <span className="font-mono text-accent text-xs">{pct}%</span>
          </div>
          <div className="h-1 bg-surface rounded-full overflow-hidden border border-border-subtle">
            <div
              className="h-full bg-accent-gradient rounded-full transition-all duration-500 ease-out shadow-glow"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Step card */}
        <Card className="animate-fade-in">
          {/* Step header */}
          <div className="mb-5">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="font-mono text-[10px] text-accent uppercase tracking-widest">
                {meta.required ? "Required" : "Optional"}
              </span>
            </div>
            <h2 className="text-lg font-bold text-text-primary font-display">
              {meta.title}
            </h2>
            <p className="text-text-secondary text-sm mt-1 font-body leading-relaxed">
              {meta.description}
            </p>
          </div>

          {/* Step content */}
          <div className="mb-6">{renderStepForm()}</div>

          {/* Step result message */}
          {typeof stepResult?.message === "string" && (
            <div className="bg-accent-muted border border-accent/20 rounded-lg px-4 py-3 mb-5">
              <p className="text-sm text-accent font-body">{stepResult.message}</p>
            </div>
          )}

          {/* Navigation buttons */}
          <div className="flex items-center gap-3 pt-2 border-t border-border-subtle">
            {step > 1 && (
              <button
                onClick={handleBack}
                disabled={loading}
                className="btn-secondary"
              >
                Back
              </button>
            )}
            <button
              onClick={handleNext}
              disabled={loading}
              className="btn-primary flex-1"
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
                className="btn-ghost"
              >
                Skip
              </button>
            )}
          </div>
        </Card>

        {/* Footer */}
        <p className="text-center text-text-muted text-xs font-mono mt-5 tracking-wide">
          Powered by Claude Desktop
        </p>
      </div>
    </div>
  );
}

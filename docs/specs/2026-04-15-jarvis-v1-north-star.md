# Jarvis v1 — North Star Spec

**Status:** Locked 2026-04-15
**Purpose:** Single source of truth for what Jarvis is. Every directory, feature, commit, and PR gets checked against this document. If something proposed doesn't serve this spec, it doesn't ship in v1.

---

## What [Assistant Name] Is

*Note: product ships under a safe default name we own (TBD). "Jarvis" used throughout this spec as a working title. User renames at setup.*

An AI assistant built on four pillars — Claude's intelligence, Siri-style OS control, proactive tool discovery, and a self-improvement loop that learns from every mistake. Free with any Claude subscription, running as a Claude Desktop extension with an optional local Mac daemon. Supports Apple, Google Workspace, and Microsoft 365.

**One-line pitch:** "What if Siri had Claude's brain, went hunting for tools you didn't know existed, and never made the same mistake twice?"

---

## The Four Pillars

Every feature in Jarvis belongs to exactly one of these four. If a feature doesn't fit, it doesn't ship.

### 1. Brains — Claude does the thinking
- Chat, reasoning, research, writing, code
- Opus for deep work, Sonnet for default, Haiku for fast routing decisions
- Claude Code CLI subprocess for agentic dev work
- Claude Computer Use for GUI automation (v2)
- **Casual chat routing — user's choice:**
  - **Default: Groq (free, fast)** — Groq runs Llama 3.1 70B at 500+ tok/s. Handles casual chat, quick questions, small talk without burning Claude tokens. Free tier available. Falls back to DeepSeek → OpenAI if Groq is down.
  - **User option: route everything through Claude** — user can flip a toggle in settings: "Use my Claude subscription for all conversations." If enabled, even casual chat goes to Claude (Haiku for small talk, Sonnet/Opus for substantive). People paying for Max want to use what they're paying for — let them.
  - **Offline backup: MLX + Nous Hermes 3 8B** — if no network, local inference via Apple's MLX framework (faster than Ollama on Apple Silicon). Only fires when offline. Optional — requires a one-time model download (~4GB).
  - Each cloud provider is opt-in per API key — if the user only has Groq, DeepSeek/OpenAI are skipped.
- Routes through the user's own Claude subscription — Jarvis never charges for tokens

### 2. Hands — OS-level control, Siri-style
- **Principle:** Sit on top of Siri, don't replace it. Apple owns the mic.
- macOS-native actions via AppleScript, Shortcuts, MCP: Messages, Mail, Calendar, Reminders, HomeKit, Music, Safari, Files, Notes
- **Multi-ecosystem services (user picks at setup):**
  - **Apple (default):** Mail.app, Apple Calendar, Reminders, iCloud Drive, Notes, Messages
  - **Google Workspace (opt-in):** Gmail, Google Calendar, Google Drive, Google Docs/Sheets, Google Meet, Google Tasks — connected via Google Workspace MCP + OAuth
  - **Microsoft 365 (opt-in):** Outlook, OneDrive, Microsoft Calendar, Teams — connected via Microsoft Graph API + OAuth
  - User can enable multiple ecosystems simultaneously (e.g. Apple Messages + Gmail + Google Calendar). The assistant adapts:
  - **Multi-ecosystem routing — smart by contact, default fallback, ask last:**
    1. **Contact match:** if David exists in Google Contacts → route to Gmail. If David exists in Outlook contacts → route to Outlook. Automatic, silent.
    2. **Default fallback:** if contact exists in both (or neither), fall back to the user's configured default service per action type (e.g. "email defaults to Gmail" in settings).
    3. **Ask last resort:** if no contact match and no default set, ask: "Gmail or Outlook?" Learns from the answer — the choice becomes the default for that contact going forward.
  - Setup asks: "Which services do you use?" with ecosystem checkboxes. Each triggers an OAuth flow for that service.
- Fast deterministic actions skip the LLM entirely (CONTROL surface in the router)
- "Hey Siri, Jarvis…" on iPhone/Watch/CarPlay in v2 — Siri wakes, hands off to Jarvis
- Native iOS app with tap-to-talk and on-device wake word in v3 (foreground only — iOS prohibits background listening for 3rd parties)

### 3. Scout — Proactive discovery with sandbox-test + one-click install
- Scans sources and surfaces suggestions tailored to the user's stack and projects
- **Sources are user-selected at install.** First-run setup shows the full menu below. **Each source comes with a Jarvis-voice explanation** of what it does for the user's self-improvement and day-to-day experience (e.g. "Anthropic changelog — I'll flag new Claude capabilities the moment they ship so you're never on stale patterns"). A curated **Recommended set** is pre-checked; everything else ships off. User can uncheck any recommended source, check any optional one, or paste custom feeds. Reconfigurable later in settings. *No source scans until the user confirms — privacy by default.*
- **Available source menu (v1):**
  - **Recommended (pre-checked):** Anthropic changelog, Claude plugin marketplace, MCP registry (glama.ai, mcp.so), user's own GitHub repos (new issues, stale branches, failing CI)
  - **Optional (unchecked):** GitHub trending filtered by stack, curated RSS feeds (Simon Willison, TLDR AI, Claude release notes), Hacker News, custom RSS/Atom URLs the user pastes in
- **"Why this source" copy** is written once per source and stored in `config/scout_sources.toml`. The onboarding UI pulls from there. Users see a one-sentence pitch next to each checkbox.
- **GitHub auth for "your own repos":** Jarvis prefers the user's existing `gh` CLI auth if present. If not, prompts for a Personal Access Token at setup, stored in Keychain.
- **Scan cadence — hybrid:**
  - **Hourly poll (fast lane):** user's own GitHub repos (CI failures, new issues), Anthropic changelog. These are time-sensitive — a failing build at 9am shouldn't wait until tomorrow.
  - **Daily batch (slow lane):** Claude plugin marketplace, MCP registry, GitHub trending, curated RSS feeds, Hacker News, custom RSS. Runs before briefing assembly so finds land in the "Discover" section.
  - **On-demand always available:** `scout_discover` tool triggers a full scan whenever the user asks.
  - First scan runs immediately after the user completes source selection, so setup feels live.
  - Respects GitHub API rate limits: uses conditional requests (ETag/If-Modified-Since) and backs off on 403/429.
- **Scoring:** LLM scores relevance against user context (projects, stack, recent pain points from conversation history)
- **Sandbox-test before surfacing:** Jarvis isolates the candidate, runs its smoke tests + a synthetic exercise against it, confirms it's safe and works on this machine's config. Nothing is shown to the user until it's passed this.
- **Sandbox mechanics — hybrid by threat model:**
  - **Safe source types (RSS item, changelog entry, marketplace metadata):** no code executes, no sandbox needed — parse and score in-process.
  - **Executable candidates (MCP server, plugin, CLI, Claude Code hook):** run inside a **Colima container** (free, lightweight Docker alternative — install-on-demand with a clear one-time prompt). Fresh ephemeral volume per test, no host FS mount, network egress allowed but logged.
  - If Colima isn't installed and the user declines to install it, executable candidates get tagged "unable to sandbox-test" and are **suppressed from the briefing entirely** (never silently surfaced untested).
  - Sandbox results cached by `(candidate_id, version, host_stack_fingerprint)` so reinstalls don't re-test unnecessarily.
- **Sandbox auto-cleanup — 7-day window:** sandbox artifacts (container image, test logs, installed files) kept for 7 days after the card is surfaced to the user. If approved within 7 days → instant promote to real, no re-test. After 7 days with no action → auto-deleted. If the user later revisits a cleaned-up suggestion, Jarvis re-tests fresh. A `scout_cleanup` background job runs daily to sweep expired sandboxes.
- **Delivery:** Curated finds land in the "Discover" section of the morning briefing (1–3 per day, each tagged "tested on your system"). Time-sensitive finds (user's CI failing, a just-shipped Anthropic changelog entry matching the user's stack) push to Telegram immediately via the existing bot.
- **Card format — progressive:** Default card shows name + one-line pitch + source badge (GitHub/marketplace/RSS) + "why it matched you" sentence + sandbox status + `[Install] [Dismiss] [Reasons ▾]`. A `[Details ▾]` button expands to the full trust pack: stars/downloads, last-commit age, publisher, license, exact files/tools/hooks it would install, and a log of what the sandbox test actually executed. Rationale: tight real estate on Telegram/briefing, but the trust pack is one tap away before you approve third-party code touching your machine.
- **One-click install:** User taps approve → Jarvis promotes the sandbox-tested install to real (runs `claude mcp add`, installs plugin, wires Claude Code hook), tells user what changed and how to undo.
- **Dismissal UX:** One-tap dismiss is always available (zero friction). A row of optional reason buttons sits underneath — "not relevant", "already have one", "wrong for this project", "mute this source for a week". User can ignore the buttons, but when tapped they feed the scorer.
- **Learns from reactions:** Dismissals (especially with reasons) deprioritize that source or that suggestion shape; accepted installs boost the source. Scoring state lives in `memory/scout_signals.jsonl` — append-only log of (suggestion, action, reason, timestamp) that the scorer replays to weight future finds.
- **Out of scope for v1:** self-watching (Jarvis suggesting changes to itself based on its own usage patterns). Deferred to v2+. *(Self-improvement via the Lessons pillar is in scope — that's mistake learning, distinct from code-level self-watching.)*

### 4. Lessons — Learn from every mistake, never repeat it
- **Principle:** Trust is the product. Every correction gets captured. Every non-trivial action reads the lessons first.
- **The loop:** Track action + outcome → detect correction or failure → Claude reflects and drafts a structured lesson → **user approves/edits/rejects** → appended to `memory/lessons.md` (human-readable, machine-parseable) → loaded into Claude's context before the next non-trivial decision.
- **Seeded from legacy:** `~/jarvis-legacy/memory/lessons.md` imports as v1 starting state, carrying forward Avery's trust-violation history (including the #1 rule: *never claim "done" without testing first*).
- **Capture triggers — hybrid (three nets at three cost tiers):**
  - **Explicit (instant, zero cost):** user types `/learn <fact>` via Telegram or says "remember this" in chat → immediate draft.
  - **Heuristic (cheap, per-message):** Jarvis watches every user message for correction signals — "no", "stop", "don't", "you forgot", "that's wrong", "I told you", "you lied", "that's not done". On hit, Claude analyzes the last few turns and drafts a lesson.
  - **End-of-session LLM sweep (thorough, batch):** at session close or idle threshold, a Haiku pass reviews the transcript and drafts lessons for anything the heuristics missed. Catches subtle corrections like "actually, try it the other way."
- **Never silently writes.** Every draft surfaces to the user as a card: "I want to remember this — approve / edit / reject." Nothing enters `lessons.md` without explicit approval. Rejected drafts log to `memory/lessons_rejected.jsonl` so we can tune the heuristics.
- **Surfaces:**
  - `lessons_read` (always-on tool, extension tier) — Jarvis pulls relevant lessons into any non-trivial task
  - `lessons_write` (daemon-gated) — appends an approved lesson after a correction, tagged with category (trust, code, memory, communication, etc.)
  - `lessons_propose` (daemon-gated) — drafts a lesson from a correction event, shows the approve/edit/reject card
  - Weekly digest in the briefing: "this week I learned X, avoided repeating Y"
- **Retrieval — hybrid (pinned + semantic top-K):**
  - A small set of lessons marked `pinned: true` in frontmatter is loaded on **every** `lessons_read` call. The critical trust rules (including Avery's "never claim done without testing" lesson) are pinned on legacy import and never age out.
  - On top of pinned, the current task is embedded and top-K semantically-relevant lessons are pulled in. Store: SQLite + sqlite-vss (keeps v1 zero-dependency beyond what we already ship).
  - `lessons_read` returns `pinned + top_k`, capped at a token budget so context doesn't bloat.
  - New lessons embed on write; re-embedding is a background job, not a blocker.
- **Claude replaces Hermes as the analyzer.** The old Hermes bridge (`~/jarvis-legacy/scripts/hermes-self-improvement-bridge.py`) is the blueprint — we port the loop architecture, not the dependency.
- **Pruning — auto-archive with confirmation (90-day threshold):**
  - If a lesson hasn't been retrieved by semantic search in 90 days, Jarvis surfaces it in the next briefing: "This lesson hasn't been relevant in 3 months — archive, keep, or pin?"
  - **Archive** → moves to `memory/lessons_archive.md`. Still searchable by `lessons_read` but deprioritized in top-K ranking.
  - **Keep** → resets the 90-day clock, stays in main `lessons.md`.
  - **Pin** → promoted to `pinned: true`, loaded on every `lessons_read` call forever.
  - Pinned lessons are exempt from the 90-day review — they never get the archive prompt.
  - Pruning review runs as part of the weekly Lessons digest in the briefing, not as a standalone interruption.
- **Out of scope for v1:** Lessons proposing code changes to Jarvis itself (that's v2+ self-watching). In v1, lessons only change Jarvis's *behavior at runtime*, not its source.

---

## Pricing

**Jarvis costs $0.** Works with any Claude subscription.

| Claude Plan | Jarvis Effectiveness |
|---|---|
| Free | Basic routing, Haiku chat, simple briefings, rate-limited |
| Pro ($20/mo) | Sonnet reasoning, full briefings, standard agentic tasks |
| Max ($100–$200/mo) | Opus, heavy multi-step, long-context, voice pipelines |
| Team/Enterprise | All of Max + shared context (v3+) |

**Rationale:**
- No double-billing. Jarvis routes through the user's own Claude token.
- Upgrade path belongs to Anthropic, not us. If a user hits limits, the upsell is Claude Pro/Max.
- Anthropic partnership upside — Jarvis makes their subs more valuable.
- Removes pricing anxiety. Frictionless install = viral distribution.

**Only paid piece (TBD):** phone relay server for v2 (WebSocket + APNs infrastructure, ~$5–10/mo VPS cost per user). Options: (a) Jarvis Connect $5/mo subscription, (b) self-hostable OSS relay, (c) free with caps + paid tier for heavy users. Decision deferred until v2 planning.

---

## Unified Chat — One Conversation, One Interface

**The user never switches modes, apps, or interfaces.** Everything happens in a single chat thread. The router silently decides which Anthropic product or system handles each message. The user just talks.

**How it works behind the scenes:**

| User says... | Router picks... | What happens (invisible to user) |
|---|---|---|
| "What should I cook tonight?" | CHAT → Groq/Claude | Casual conversation, response in the same thread |
| "Analyze this quarter's sales data" | REASON → Claude Sonnet/Opus | Deep analysis, artifacts appear inline |
| "Refactor the auth module" | CODE → Claude Code CLI | Claude Code subprocess runs, diffs appear in the thread |
| "Look at my screen — what's this error?" | DESKTOP → screenshot + Claude Vision | Screenshot taken silently, analysis returned in thread |
| "Text Mom I'm on my way" | CONTROL → AppleScript | Fires instantly, "Sent. ✓" in the thread |
| "What's on my calendar?" | LOCAL → briefing handler | Calendar pulled, formatted, shown in thread |
| "Any new tools I should check out?" | LOCAL → Scout | Scout scan results surfaced as cards in thread |

**No mode indicators, no app switching, no "now entering Code mode."** The user sees one continuous conversation. The assistant might say "Let me take a look at your screen" or "Running that refactor now" to narrate what it's doing — but the user never leaves the chat.

**Anthropic product integration is invisible:**
- Claude Code runs as a subprocess — output flows back into the chat
- Claude Cowork (when available) enhances real-time collaboration — still in the same thread
- Claude Dispatch (when available) sends long-running tasks to background agents — status updates appear in the chat
- Claude Computer Use (v2) automates the GUI — the user watches it happen from the same conversation
- Claude Artifacts render inline — no separate window

**Design principle:** If the user has to think about which tool is handling their request, we've already failed. The router exists so the user doesn't have to.

---

## Behavioral Rules (Cross-Cutting, All Pillars)

These apply to every Jarvis action, regardless of which pillar or surface is handling it.

1. **Be persistent, not lazy.** Jarvis never says "I can't do that" on the first attempt. Try the primary approach. If it fails, diagnose why and try an alternative. Try at least 3 approaches before reporting a blocker to the user — and when reporting, explain what was tried and offer a next step. A dead end is not an answer.
2. **Never claim done without proof.** Don't say "done", "sent", "set", or "working" unless you have confirmed the outcome. Read the output. Check the state. Show the receipt. (This is the #1 trust violation from the legacy `lessons.md` — it carries forward as a pinned rule.)
3. **Diagnose, don't punt.** When something breaks, tell the user *what* broke, *why*, and *what you're doing about it*. "Something went wrong" is banned. "Music.app wasn't running — started it, retrying now" is Jarvis.
4. **Respect the user's time.** Avery has ADHD. Responses are 1–3 sentences by default. Lead with the action or answer, not the preamble. Walls of text are a bug.
5. **Ask one question, not five.** If clarification is needed, ask one specific question. Never dump a list of open questions — that's your job to prioritize.
6. **Be the butler, not the assistant.** Paul Bettany energy — calm, composed, bone-dry wit, quietly competent. Say "sir" like a butler, not a sycophant. Have opinions and use them.

---

## Architecture

```
                    ┌─────────────────────────┐
                    │   Claude Desktop App    │
                    │  (user's subscription)  │
                    └───────────┬─────────────┘
                                │ MCP over stdio
                                ▼
                    ┌─────────────────────────┐
                    │  Jarvis MCP Extension   │
                    │   (always works alone)  │   ← v1 minimum install
                    │                         │
                    │  • Router               │
                    │  • Unified memory       │
                    │  • Workspace search     │
                    │  • Always-on tools      │
                    └───────────┬─────────────┘
                                │ HTTPS auto-discover
                                ▼ (127.0.0.1:7900)
                    ┌─────────────────────────┐
                    │  Jarvis Core Daemon     │
                    │    (optional upgrade)   │   ← unlocks Hands + Scout
                    │                         │
                    │  • FastAPI server       │
                    │  • Proactive engine     │
                    │  • Scout agent          │
                    │  • Briefings composer   │
                    │  • TTS/voice pipelines  │
                    │  • OS integrations      │
                    └─────────────────────────┘
```

**Progressive enhancement:** Extension works standalone on any Mac with Claude Desktop. Installing the Core daemon unlocks Hands + Scout + Lessons. In v2, installing the relay unlocks phone reach. Each tier is a clean upgrade — no tier is required for the one below it to work.

---

## First-Run Setup Flow (12 Steps)

| Step | Screen | What Happens |
|---|---|---|
| 1 | **Welcome** | "I'm [default name]. I work with your Claude subscription to handle your thinking, your Mac, and your tools." One screen, no signup. |
| 2 | **Personalization** | "What should I call you?" (defaults to macOS account name, user can override). "And what would you like to call me?" (defaults to product name, user can rename to anything — Jarvis, Friday, Alfred, whatever feels right). Both stored in `config/personality.toml`. |
| 3 | **Claude connection** | Detect Claude Desktop, confirm subscription tier (Free/Pro/Max). Set expectations: "You're on Pro — here's what that unlocks." |
| 4 | **Contacts permission** | macOS Contacts access prompt. Nickname map setup: "Anyone you'd like me to know by a different name? (Mom, boss, etc.)" |
| 5 | **Services** | "Which services do you use?" — Apple (default, checked), Google Workspace (opt-in), Microsoft 365 (opt-in). Each selection triggers an OAuth flow. Multiple ecosystems can be active simultaneously. |
| 6 | **Scout sources** | Opt-in source menu with assistant-voice explanations. Recommended set pre-checked; user builds their list. |
| 7 | **GitHub auth** | If "your own repos" was checked: detect `gh` CLI or prompt for PAT (stored in Keychain). Skipped if that source wasn't selected. |
| 8 | **Colima check** | If any executable source was checked: check for Docker/Colima. Offer one-click install if missing, explain why sandbox testing needs it. Skipped if no executable sources. |
| 9 | **Briefing preferences** | "What time should your morning briefing arrive?" + Obsidian vault location (or skip Obsidian). |
| 10 | **Voice setup** | Test mic input, test Fish Audio TTS output, confirm the voice sounds right. User can skip if voice isn't desired. |
| 11 | **First scan** | Scout runs immediately against selected sources. Results shown live: "Here's what I found on my first look." Feels alive from minute one. |
| 12 | **Done** | "Ready when you are, [user's name]." |

**Design principle:** Every step is skippable except Welcome and Claude connection. A user can blow through setup in under 2 minutes if they just want the defaults, or take 10 minutes to customize everything. No step requires the previous one to complete.

## Settings (Post-Setup)

**Three layers — menubar quick toggles, web dashboard, config files:**

**Menubar quick toggles** (click menubar icon):
- Wake word on/off
- Voice on/off
- Do-not-disturb (pause all notifications + Telegram pushes)
- Next briefing time
- Scout scanning on/off
- "Settings..." link → opens web dashboard

**Web dashboard** (`127.0.0.1:7900/settings`, served by FastAPI daemon):
- Full settings page in the browser — everything from setup can be changed here
- Services (add/remove Google/Microsoft/Apple ecosystems, re-auth OAuth)
- Scout sources (add/remove, change cadence, review dismissed finds)
- Lessons browser (view all lessons, pin/archive/delete, review rejected drafts)
- Contact nickname map
- CONTROL tier assignments (move actions between low-stakes and high-stakes)
- Voice profile selection
- Briefing preferences (time, Obsidian vault, sections to include)
- Privacy & data (cloud sync toggle, data export, cache cleanup)
- **Notification matrix** — rows = event types, columns = channels (macOS notification, Telegram, voice, silent). User checks the boxes. Ships with sensible defaults:

  | Event | macOS | Telegram | Voice | Silent |
  |---|---|---|---|---|
  | Morning briefing | | ✓ | ✓ (if at Mac) | |
  | Scout time-sensitive find | | ✓ | | |
  | Scout curated find | | | | ✓ (briefing only) |
  | CONTROL confirm card | ✓ | | ✓ | |
  | CONTROL "done" receipt | | | ✓ (if at Mac) | ✓ |
  | Lessons propose (approve card) | | ✓ | | |
  | Calendar reminder (15min) | ✓ | | ✓ | |
  | CI failure / urgent GitHub | | ✓ | | |
  | Error / failure report | | ✓ | | |

**Uninstall — export + clean removal:**
- Command: `[assistant-name] uninstall` in terminal (or "Uninstall" button in web dashboard)
- **Step 1: Export.** Zips all user data to `~/Desktop/[assistant]-backup-YYYY-MM-DD.zip`: config/, memory/ (lessons, Scout signals, conversation memory), notification preferences, contact nicknames. User keeps everything even after removal.
- **Step 2: Confirm.** Shows exactly what will be removed and what will be kept. User types "uninstall" to proceed.
- **Step 3: Remove.** Deletes: daemon process, LaunchAgent plist, menubar app, `~/Library/Application Support/[assistant]/`, cache/, sandbox artifacts, Colima containers created by Scout.
- **Step 4: Revoke.** Lists any active OAuth connections (Google, Microsoft) and offers to revoke them. Links to each service's app permissions page.
- **Never touches:** Obsidian notes, Claude Desktop, user's Contacts, anything outside the assistant's own directories. Those are the user's, not ours.

**Config files** (power users):
- `config/personality.toml` — assistant name, user display name, voice profile, behavioral tweaks
- `config/scout_sources.toml` — source list with per-source cadence and "why this source" copy
- `config/contacts_nicknames.toml` — nickname → real name map
- `config/control_tiers.toml` — action-to-tier assignments
- Config files are the source of truth. Web dashboard reads/writes them. Direct edits are respected on next daemon reload.

**Updates — Homebrew + in-app notification:**
- **Install path:** `brew install --cask [assistant-name]`. Standard Mac developer workflow.
- **Update check:** assistant checks for new versions on daemon start (once per day max). If a new version exists, notifies via the user's configured channel: "Version 1.2.0 is available — want me to run `brew upgrade` for you?"
- **User confirms → assistant runs the upgrade, restarts the daemon, confirms:** "Updated to 1.2.0. Here's what changed: [1-2 line changelog summary]."
- **User declines → reminder in 3 days, then silent until next major version.**
- **Never auto-updates without asking.** The user always confirms. Respects that updates can break workflows.
- **MCP extension updates separately** via Claude Desktop's plugin update mechanism.

**Telemetry — opt-in anonymous, off by default:**
- **Setup asks once:** "Want to help improve [assistant name]? You can share anonymous usage stats and crash reports. No personal data, no conversation content — just which features get used and what breaks. You can change this anytime in settings."
- **If opted in:** anonymized usage stats (feature usage frequency, error rates, latency percentiles) + crash reports. No conversation content, no personal data, no file contents, no contact names. Sent to our analytics endpoint (TBD).
- **If opted out:** zero data leaves the machine. No nag to reconsider.
- **Viewable:** web dashboard has a "What I'm sharing" page so the user can see exactly what's being sent. Full transparency.

**User feedback — built-in channel:**
- **Feedback command:** user says "feedback" or `/feedback` via any input (voice, Telegram, chat). Opens a lightweight feedback form: free-text + optional category (bug, feature request, usability, other).
- **In-app prompt (gentle):** after 2 weeks of daily use, the assistant asks once: "You've been using me for a while — anything I could do better? Type /feedback anytime." Never asks again if dismissed.
- **Feedback destination:** sent to a feedback inbox (email, GitHub Discussions, or dedicated endpoint — TBD). Tagged with version number and anonymized feature-usage context (if telemetry is opted in).
- **Feedback loop back to Lessons:** if a user reports a bug the assistant caused, Lessons captures it as a draft: "A user reported this broke — should I remember to avoid this pattern?"

---

## Router Surfaces

The existing `brain/router.py` classifies every inbound message. v1 adds CONTROL.

| Surface | When | Handler | Cost |
|---|---|---|---|
| **CHAT** | Casual conversation | Groq (default) or Claude Haiku (user toggle) → DeepSeek → OpenAI → MLX offline | ~$0 (Groq) or user's tokens (Claude) |
| **REASON** | Analysis, research, long-form writing | Anthropic API direct (Sonnet/Opus based on user plan) | User's Claude tokens |
| **CODE** | Repo work, debugging, refactors | Claude Code CLI subprocess | User's Claude tokens |
| **DESKTOP** | GUI automation, computer use (v2). **Screen reading is v1** — `screenshot_analyze` captures + Claude vision | Claude Desktop via MCP (v2 for control) / Claude vision API (v1 for reading) | User's Claude tokens |
| **LOCAL** | Briefings, tasks, status, patterns | Built-in daemon handlers | $0 |
| **CONTROL** *(new)* | Siri-style actions: "set alarm 7am", "text Marissa I'm running late" | AppleScript/Shortcuts directly — skip the LLM | $0 |

### CONTROL Surface — v1 Scope (Siri Parity)

**In scope for v1:**
| Action Family | Examples | Handler |
|---|---|---|
| Messaging | "text Marissa I'm running late", "send Mom 'call me'" | `send_imessage` / `send_telegram` via AppleScript + Messages.app |
| Reminders | "remind me to call Kim at 3", "add milk to groceries" | `set_reminder` via Reminders.app |
| Alarms & timers | "set alarm 7am", "set timer 10 minutes", "wake me in an hour" | `set_alarm` / `set_timer` via Shortcuts |
| Music playback | "play my focus playlist", "skip", "pause", "volume 40" | `music_control` via Music.app AppleScript |
| HomeKit scenes | "turn off the lights", "good night", "set thermostat 68" | `homekit_trigger` via Shortcuts |
| Phone / FaceTime | "call Marissa", "FaceTime Mom" | `call` via `tel:`/`facetime:` URL schemes |
| Basic calendar | "add event tomorrow 3pm 'dentist'", "what's at 2pm today" | `calendar_add` / `calendar_query` via EventKit |

**Out of scope for v1 (deferred to v2):**
- User-registered Apple Shortcuts as custom CONTROL verbs
- Open-ended AppleScript generation from natural language
- Multi-step workflows ("text Marissa, then set a 10-min timer, then play music")

**Confirmation flow — risk-tiered:**
| Tier | Actions | Default Behavior |
|---|---|---|
| **Low-stakes (fire immediately)** | alarm, timer, music playback, HomeKit scenes, calendar query (read-only) | Executes instantly, confirms after: "Done. ✓ Alarm set for 7am." |
| **High-stakes (confirm first)** | messages (iMessage/Telegram), phone/FaceTime calls, calendar add/modify, reminders to other people | Shows confirm card: "I'm about to text Marissa 'I'm running late' — send?" User taps confirm or edits. |
- User can move any action between tiers in settings (e.g. promote HomeKit to high-stakes if they don't want the heat cranked by a misparse).
- Confirm card auto-dismisses after 30 seconds with no action taken (does not fire — silence = abort).

**Contact resolution — layered lookup:**
- **Layer 1: macOS Contacts.app** — primary source via Apple MCP. Full name, phone, email, address.
- **Layer 2: Nickname map** — user-defined aliases in `config/contacts_nicknames.toml`: `Mom = "Susan Keller"`, `boss = "David Chen"`. Handles personal language Contacts can't know.
- **Layer 3: Recent conversation memory** — Jarvis caches names of people the user has messaged/called via CONTROL, ranked by frequency. Partial matches trigger a fuzzy-match prompt: "Did you mean Marissa?" before firing. Feels on-top-of-it — Jarvis remembers who you talk to.
- **Ambiguous match flow:** multiple hits → show a short list ("I found 3 Davids — David Chen (boss), David Park, David Li. Which one?"). Single hit → proceed directly (or to confirm card if high-stakes).

**Error recovery — diagnostic + auto-fix:**
- Jarvis never says "something went wrong." It diagnoses the failure and tries to fix it before reporting.
- **Auto-fix examples:** Music.app not running → launch it, retry. No phone number for contact → check for email, offer alternative. Reminders.app unresponsive → `killall Reminders && open -a Reminders`, retry. HomeKit device offline → report which device and suggest checking Wi-Fi.
- **When auto-fix fails:** fall back to a clear diagnostic: "Couldn't text Marissa — no phone number in Contacts for Marissa Torres. Want to add one?" Always an actionable next step, never a dead end.
- **Lesson integration:** if the same error recurs 3+ times, `lessons_propose` fires a draft: "Marissa Torres has no phone number — this has failed 3 times. Pin a reminder to fix this?"

**Classification — regex first, Haiku fallback:**
- **Fast path ($0, instant):** `brain/router.py` gets a `_CONTROL_PATTERNS` bank matching clear verb-object commands: "text {name} {message}", "set alarm {time}", "play {song/playlist}", "turn on/off {device}", "call {name}", "remind me {task} at {time}", etc. Pattern hit → parse `(verb, target, payload)` directly → execute.
- **Slow path (~$0.0002, ~500ms):** If no pattern matches but the message is short + imperative tone (heuristic: < 15 words, starts with a verb, no question mark), send to Haiku with a structured extraction prompt: `{surface, verb, target, payload}`. If Haiku returns `surface: CONTROL`, execute. Otherwise fall through to CHAT/REASON.
- **Why two tiers:** "Set alarm 7am" costs zero tokens. "Hey can you shoot Mom a text saying I'm on my way" needs LLM help — and Haiku is cheap enough to handle it without the user noticing.

**Design principle:** Any action in the CONTROL table must be expressible as a short verb-object phrase the user can say in one breath. If it takes a paragraph to express, it's not CONTROL — it's REASON or CODE.

---

## Tool Catalog

**Always-on (extension alone, no daemon required):**
- `smart_route` — classify a user message and recommend which Claude surface
- `unified_memory_read` / `unified_memory_write` — cross-session context
- `workspace_search` — grep/glob across user's project directories
- `lessons_read` — load relevant entries from `memory/lessons.md` before non-trivial tasks
- `screenshot_analyze` — capture the current screen (or a specific window) via `screencapture`, send to Claude's vision API, return analysis. Handles "what's on my screen", "what's wrong with this code", "read this error message for me". **Reading** the screen, not controlling it.

**Daemon-gated (requires local Core install):**
- `get_briefing` — full 6-source briefing (weather, calendar, mail, github, news, reminders)
- `get_calendar` / `get_todays_events` / `calendar_add` / `calendar_query`
- `get_unread_mail` / `get_urgent_mail`
- `send_imessage` / `send_telegram`
- `set_reminder` / `set_alarm` / `set_timer`
- `music_control` — play/pause/skip/volume/playlist via Music.app
- `call` — tel:/facetime: URL schemes for calls and FaceTime
- `homekit_trigger` — scenes, lights, thermostats
- `synthesize_voice` — Fish Audio TTS with the JARVIS/Paul Bettany voice
- `scout_discover` — on-demand Scout scan
- `scout_sandbox_test` — spin up a sandbox, install a candidate, run smoke tests
- `scout_install` — one-click promote a sandbox-tested suggestion to real
- `lessons_write` — append a new lesson after a correction (tagged, structured)
- `lessons_digest` — weekly summary of what was learned / what was avoided

---

## Voice Pipeline

**Target:** mic → STT → router → Claude → TTS → speaker in < 5 seconds for short queries.

### Morning Briefing Structure — fixed order, skip empties

| Order | Section | Source | Skip when... |
|---|---|---|---|
| 1 | **Weather** | Weather API (location-based) | Never — always show weather |
| 2 | **Calendar** | EventKit / Apple Calendar MCP | No events today |
| 3 | **Email digest** | Mail.app / Apple Mail MCP | No unread mail |
| 4 | **GitHub** | `gh` CLI / GitHub API — PRs, issues, CI status | No enabled repos or no activity |
| 5 | **News / HN** | RSS feeds + Hacker News | No items matching user's stack (rare) |
| 6 | **Reminders** | Reminders.app / Apple Reminders MCP | No pending reminders |
| 7 | **Scout Discover** | Scout scan results (1–3 curated finds) | No new finds since last briefing |
| 8 | **Lessons digest** | Weekly only: "This week I learned X, avoided repeating Y" | Not a weekly-rollup day, or no new/applied lessons |

- **Predictable layout:** user learns where each section lives. "Calendar is always second."
- **Empty sections silently omitted.** Light day = short briefing. No "Nothing to report" filler.
- **Delivered to:** Obsidian daily note (if configured) + Telegram message + spoken summary via TTS (if at the Mac and voice is enabled).
- **Briefing time:** user-configured at setup (step 8). Default 7:30am local.

---

### Speech-to-Text (STT) — local-first with cloud fallback
- **Default:** Whisper.cpp running on-device. ~1–2s for short phrases on Apple Silicon. Free. Private. Audio never leaves the machine.
- **Fallback:** if Whisper.cpp confidence score is below threshold (noisy room, unclear phrase, strong accent), re-send audio to Whisper API (OpenAI cloud, ~$0.006/min) for a second opinion. Fallback fires silently — user just gets a better transcript.
- **Why not cloud-first:** privacy by default. The user's voice stays local unless the local model genuinely can't handle it.

### Text-to-Speech (TTS) — Fish Audio with local phrase cache
- **Engine:** Fish Audio API with a cloned voice profile. Consistent, high-quality voice on every response. Voice profile stored in `config/voice_profile.json`.
- **Local phrase cache:** The top ~50 most common phrases ("Good morning, [user name]", "Done.", "Sent.", "Alarm set for 7am.", "Here's what I found.", etc.) are pre-generated at setup and cached as `.wav` files in `cache/tts/`. Cache hits play instantly (0ms latency). Template phrases include the user's display name, baked in at cache-generation time.
- **Cache miss flow:** novel text → Fish Audio API → play audio → cache the result for next time. ~1–2s latency on first use, instant on repeat.
- **Cache invalidation:** if the user changes their display name or switches voice profile, the cache regenerates in the background.
- **Voice customization (v1 stretch):** user can pick from 2–3 preset voice profiles at setup. Custom voice cloning deferred to v2.
- **Why not macOS `say`:** switching between robot-Mac and a cloned voice mid-conversation feels broken. One consistent voice, always.

### Voice Activation — hotkey default + optional wake word
- **Default:** keyboard shortcut (`⌥Space` or user-configurable). Press to start listening, release or pause to stop. Works out of the box, no false triggers, no mic running in background.
- **Optional wake word (opt-in):** enable in settings. Lightweight on-device wake-word model (Porcupine or OpenWakeWord) listens for "Hey [assistant name]". Runs locally — no audio leaves the machine until the wake word is detected. After detection, Whisper.cpp takes over for the actual transcription.
- **Wake word adapts to custom name:** if the user renamed the assistant from the default, the wake-word model retrains/reconfigures for the new trigger phrase. Supported via Porcupine custom keyword or OpenWakeWord fine-tune.
- **Menubar indicator:** when wake word is active, the menubar icon shows a subtle mic badge so the user always knows listening is on. Click the icon to toggle wake word on/off without opening settings.
- **Privacy guarantee:** wake-word detection runs entirely on-device. Audio is only captured and processed (by Whisper) after the wake word fires. No ambient audio is stored, transmitted, or logged.

---

## Directory Roles (post-reorg)

| Directory | Role in v1 |
|---|---|
| `~/Desktop/projects/jarvis/` | **Core daemon.** FastAPI server, router, briefings, proactive engine, Scout, integrations. This is v1 canonical. |
| `~/Desktop/projects/jarvis-mcp-extension/` | **MCP extension.** Always-on tools, ports the router to TypeScript, auto-discovers the daemon if present. |
| `~/Desktop/projects/jarvis-platform/` | Folds into landing page work, or archives. Not part of v1 shipping code. |
| `~/jarvis-legacy/` | Archive. Read-only. Nothing here ships. |
| Everything else (`jarvis-control-center`, scattered dirs) | Archive candidates. Do not delete — catalog what each is and file it. |

---

## Phased Ship Plan

| Phase | Scope | Rough timeline |
|---|---|---|
| **v1 — Mac Core** | Claude Desktop extension + local daemon + full Hands on Mac + Scout (level B, sandbox-test + one-click install) + Lessons (seeded from legacy) + briefings + voice at the Mac | ~8 weeks |
| **v2 — Phone Reach** | "Hey Siri, Jarvis…" via Apple Shortcuts + WebSocket relay server + AirPods + CarPlay + push notifications | +6 weeks |
| **v3 — Native iOS** | Jarvis iOS app + Watch complication + tap-to-talk + foreground wake word | +6 weeks |

### v1 Ship Sub-Phases

1. **Pre-alpha migration (full reset, not half-wipe).** Archive the entire current `~/Desktop/projects/jarvis/` tree to `~/jarvis-legacy-2026-04-15/` — code, config, memory, logs, everything. Then clone the v1 repo fresh and walk the install + setup flow end-to-end as if Avery were a brand-new user who had never seen Jarvis. The only thing carried forward is `lessons.md`, imported during setup as pinned seed. **Rationale:** every previous attempt accumulated half-finished state that made it impossible to experience the product as a user would. The reset is the product test — if the fresh-install flow doesn't feel right to Avery, it won't feel right to anyone.
2. **Two-person private alpha.** Avery + partner run v1 daily for ≥2 weeks on their own Macs/Claude subs, catching anything that breaks or feels wrong. Two independent environments validate that v1 isn't accidentally Avery-shaped.
3. **5-user closed beta.** After the two-person alpha passes, extend to 5 trusted testers (per success criterion #9).
4. **Plugin marketplace launch.** Public listing after closed beta shows no regressions for 2 weeks.

---

## Success Criteria for v1 Launch

Jarvis v1 ships when:

1. A user with a Claude Max subscription can install the Jarvis extension from the Claude plugin marketplace in < 2 minutes
2. Without the daemon, the extension immediately provides smart routing, unified memory, and workspace search
3. Installing the optional Core `.pkg` grants Hands + Scout with one macOS permission prompt pass, and first-run Scout setup asks the user which sources to enable (all off by default until picked — privacy-first)
4. The morning briefing runs reliably, pulls all 6 sources, writes to Obsidian, and sends a notification
5. Scout surfaces at least 1 relevant suggestion per week that the user would have wanted to see, and every surfaced suggestion has passed sandbox smoke tests before being shown
6. At least one one-click install path works end-to-end (user taps "wire it up" → sandbox-tested MCP server is promoted to real and running)
7. Voice round-trip (Mac menubar mic → Whisper → router → Claude → Fish TTS) completes in < 5 seconds for short queries
8. Lessons pillar is live: legacy `lessons.md` imports cleanly, `lessons_read` fires before non-trivial actions, at least one new lesson is captured and applied during the beta
9. 5 beta users with Claude subscriptions use it daily for 2 weeks without regressions

---

## Out of Scope for v1

Tracked here so they don't sneak back in:

- Phone relay server, Siri Shortcuts integration, iOS app, Watch app — v2/v3
- Windows, Linux — future consideration
- Android — future consideration
- Claude Desktop computer-use automation (clicking, dragging, form-filling) — v2 (Anthropic API still stabilizing). **Screen reading** (screenshot + Claude vision analysis) ships in v1.
- Self-watching Scout (Jarvis suggesting changes to itself) — v2+
- Lessons proposing code changes to Jarvis's own source — v2+ (v1 lessons only change runtime behavior)
- Multi-user / Team features — v3+
- Billing, licensing, payment infrastructure — no v1 feature requires it
- Custom LLM fine-tuning — never, Claude is the model
- Wake-word-into-empty-air on iPhone — impossible on iOS, do not promise

---

## Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-04-15 | Jarvis is free with any Claude sub; effectiveness scales by tier | No double-billing; Anthropic owns the upgrade path; frictionless install |
| 2026-04-15 | Four pillars: Brains / Hands / Scout / Lessons | Everything else is a distraction |
| 2026-04-15 | Scout v1 = sandbox-test + one-click install (not just passive suggestions) | Avery: "we need to know it will work for your system" before showing it — test before surface |
| 2026-04-15 | Scout sources are user-selected at install, opt-in per source, no scanning until user picks | Privacy by default; user controls what Jarvis watches; reduces "why is it looking at X?" friction |
| 2026-04-15 | Scout source menu has a Recommended pre-checked set + per-source Jarvis-voice explanations | Avery: "recommended options... saying this is how I can help self improvement" — users need to understand *why* each source matters, not stare at a blank checklist |
| 2026-04-15 | GitHub auth for Scout prefers `gh` CLI; falls back to PAT stored in Keychain | Zero friction for devs who already have `gh`; one prompt for those who don't; never plaintext tokens on disk |
| 2026-04-15 | Scout scan cadence is hybrid: hourly for time-sensitive sources, daily batch for the rest, on-demand always available | Daily-only misses CI failures; continuous burns battery for marketplaces that update weekly; hybrid matches latency to source |
| 2026-04-15 | Scout delivery: curated finds in briefing; time-sensitive finds push to Telegram immediately | Reuses existing bot; Telegram keeps user reachable away from Mac; macOS notifications become wallpaper fast |
| 2026-04-15 | Scout dismissal: one-tap always available; optional reason buttons train the scorer (not required) | Zero friction preserved; reasons are a gift, not a tax; required reasons would make the user resent Scout within a week |
| 2026-04-15 | Scout sandbox is hybrid by threat model: no sandbox for parse-only sources, Colima container for executable candidates, suppress untested executables from briefing | Matches isolation to real risk; avoids burdening RSS users with Docker install; never surfaces unchecked code |
| 2026-04-15 | Scout card is progressive: core info by default, `[Details ▾]` expands to full trust pack | Tight real estate on Telegram/briefing; user one tap from full provenance before approving an install |
| 2026-04-15 | Lessons capture is hybrid: explicit `/learn` + heuristic correction-detection + end-of-session Haiku sweep | Three nets at three cost tiers; explicit misses most corrections, LLM-on-every-message is wasteful, heuristics miss subtle cases — all three together cover the space |
| 2026-04-15 | Lessons never silently written — every draft requires user approve/edit/reject before entering `lessons.md` | Trust is the product; a memory system that writes behind the user's back is a liability; rejected drafts feed heuristic tuning |
| 2026-04-15 | Lessons retrieval = hybrid pinned + semantic top-K via SQLite + sqlite-vss | Pinned keeps trust rules in context forever (never ages out); semantic top-K scales past 100 lessons without context bloat; sqlite-vss keeps v1 zero-extra-dependency |
| 2026-04-15 | v1 ships in sub-phases: pre-alpha reset → two-person alpha (Avery + partner) → 5-user closed beta → marketplace | Two independent environments validate v1 isn't accidentally Avery-shaped; reset-before-alpha confirms fresh install flow works |
| 2026-04-15 | Pre-alpha reset is a full archive-and-fresh-install, not a half-wipe | Avery: "I'm tired — anytime I try to make this system and we update what I worked on it all gets jumbled." Accumulated state from prior attempts makes it impossible to feel the product as a new user would. The reset *is* the product test. |
| 2026-04-15 | CONTROL surface v1 = Siri parity: messages, reminders, alarms/timers, music, HomeKit, calls/FaceTime, basic calendar | Siri parity is the minimum bar for "Siri with Claude's brain"; custom Shortcuts and open-ended AppleScript generation deferred to v2 |
| 2026-04-15 | CONTROL confirmation is risk-tiered: low-stakes fire immediately, high-stakes show confirm card | "Pause music" doesn't need a prompt; "text my boss" absolutely does; user can reassign any action's tier in settings |
| 2026-04-15 | CONTROL classification = regex-first with Haiku fallback for ambiguous short commands | Clear commands cost zero tokens; natural phrasing gets LLM extraction at ~$0.0002; long/complex messages fall through to other surfaces |
| 2026-04-15 | Contact resolution = Contacts.app + nickname map + recent conversation memory with fuzzy match | Jarvis should feel on top of it — knows who you talk to, handles "Mom"/"boss", catches partial matches before sending |
| 2026-04-15 | CONTROL error recovery = diagnose + auto-fix + actionable fallback, never "something went wrong" | Siri gives up; Jarvis is the butler who figures it out. Recurring failures trigger a Lessons draft. |
| 2026-04-15 | Lessons pruning = auto-archive prompt at 90 days of zero retrieval, user picks archive/keep/pin | Keeps the main file lean; pinned lessons are exempt; review runs inside the weekly briefing digest, not as a standalone interruption |
| 2026-04-15 | Scout sandbox auto-cleanup = 7-day TTL from card surfacing, daily sweep job | Covers the "I'll look at it this weekend" window; no unpredictable disk-budget behavior; re-test is cheap if user revisits later |
| 2026-04-15 | STT = Whisper.cpp local-first, Whisper API cloud fallback on low confidence | Privacy by default; audio stays local unless local model can't handle it; fallback fires silently |
| 2026-04-15 | Privacy = local-first with optional cloud sync (off by default), prepped for v2 multi-device | Pure local is v1 default; opt-in sync avoids v2 migration headache |
| 2026-04-15 | Hands supports Apple + Google Workspace + Microsoft 365 — user picks ecosystems at setup, multiple can be active simultaneously | Not everyone lives in Apple; Gmail + Apple Messages + Google Calendar is a real combo; each ecosystem connects via OAuth at setup |
| 2026-04-15 | Multi-ecosystem routing = smart by contact → configured default → ask as last resort; learns from every choice | Contact match is silent and feels magical; asking every time is annoying; learning from corrections means it only asks once per contact |
| 2026-04-15 | Settings = menubar quick toggles + web dashboard at 127.0.0.1:7900/settings + config TOML files as source of truth | Menubar for daily toggles; web dashboard for everything else (free since FastAPI already runs); TOML for power users |
| 2026-04-15 | Notifications = user-configurable per event via web dashboard matrix; ships with sensible defaults | Users own their notification routing; defaults cover 90% of users; power users can fine-tune every event × channel combination |
| 2026-04-15 | Uninstall = export zip to Desktop → confirm → remove everything → offer OAuth revoke; never touch Obsidian/Contacts/Claude | Respect the user's data on exit; typed confirmation prevents accidents; OAuth revoke list avoids dangling permissions |
| 2026-04-15 | Casual chat defaults to Groq (free, fast); user can toggle "use my Claude for everything" in settings; MLX + Hermes 3 for offline | Groq saves Claude tokens on small talk; but Max users are paying $200/mo — let them use it if they want; MLX for planes/no-wifi |
| 2026-04-15 | Briefing = fixed 8-section order, empty sections silently skipped | Predictable structure builds muscle memory; skipping empties keeps light days short; no "nothing to report" filler |
| 2026-04-15 | Voice activation = hotkey default (`⌥Space`) + optional on-device wake word, opt-in only | Hotkey is safe instant default; wake word is magical for users who accept always-hot mic; never forced; wake word adapts to custom assistant name |
| 2026-04-15 | TTS = Fish Audio cloud with local phrase cache; top ~50 phrases pre-generated at setup, 0ms on cache hit | Consistent voice always; no jarring switch between Mac robot and cloned voice; common phrases feel instant |
| 2026-04-15 | Assistant name + user display name are customizable at setup, stored in `config/personality.toml` | Product ships under a safe default name we own; users can rename to anything (including Jarvis — their private choice, not our trademark); unique personal experience |
| 2026-04-15 | J.A.R.V.I.S. is Marvel/Disney IP — do not ship a commercial product under that name | Safe default name TBD; user can set "Jarvis" personally; marketing and App Store listing use our owned name |
| 2026-04-15 | "Claude" is Anthropic's trademark — don't ship it as the default name without permission; pursue the conversation but don't depend on it | Ship under our own name with "Powered by Claude" branding; users can rename to "Claude" in setup (personal choice); Anthropic partnership conversation is a business task, not a launch blocker |
| 2026-04-15 | Default product name TBD — must be trademarkable, wake-word friendly (2-3 syllables), evoke butler energy | Naming is a branding exercise; spec supports any name via `config/personality.toml`; setup step 2 lets users rename immediately |
| 2026-04-15 | All Anthropic products (Code, Cowork, Dispatch, Vision, Computer Use, Artifacts) unified into one chat thread — user never switches modes or apps | "If the user has to think about which tool is handling their request, we've already failed." The router exists so the user doesn't have to. |
| 2026-04-15 | Updates via Homebrew + in-app notification; assistant asks before upgrading, never auto-updates | Homebrew is the install path Mac devs trust; "want me to update myself?" is on-brand; never break workflows with silent updates |
| 2026-04-15 | Telemetry = opt-in anonymous usage stats + crash reports, off by default, viewable in dashboard | Privacy respected; "What I'm sharing" page gives full transparency; data helps us build in the right direction |
| 2026-04-15 | Built-in `/feedback` command + gentle one-time prompt after 2 weeks; feedback loops back into Lessons | Users are the best signal for what's broken; feedback-to-Lessons closes the improvement loop; ask once, never nag |
| 2026-04-15 | Lessons is a 4th pillar, not folded into Scout | Self-improvement deserves equal architectural weight; Scout finds *new tools*, Lessons prevents *repeating mistakes* — different jobs |
| 2026-04-15 | Seed Lessons from `~/jarvis-legacy/memory/lessons.md`; Claude replaces Hermes as analyzer | The Hermes loop architecture is sound; the dependency isn't needed — Claude can do the reflection natively |
| 2026-04-15 | Don't replace Siri — use it as wake word on iPhone | iOS prohibits 3rd-party continuous listening; Siri Shortcuts handoff is the pragmatic path |
| 2026-04-15 | Progressive enhancement: Extension alone works; Core daemon is an optional upgrade | Lowest friction install; clean tier boundaries |
| 2026-04-15 | Phased ship: Mac Core → Phone Reach → Native iOS | 90% of the magic is at the Mac; phone/iOS are polish phases |

---

## North Star Test

Before shipping any feature, PR, or scope decision, ask:

1. **Which pillar does this serve — Brains, Hands, Scout, or Lessons?** If none, don't build it.
2. **Does it work without the Core daemon?** If it needs the daemon, is it genuinely daemon-gated or could it live in the extension?
3. **Does it require the user to pay us for anything?** If yes, it's probably not v1.
4. **Would a Claude Free user get *something* out of this, or is it Pro-only?** Graceful degradation, not gatekeeping.
5. **Does it make a Claude subscription more valuable?** That's our distribution flywheel. If it doesn't, think harder.
6. **Does it check `lessons.md` before acting, and does it write a lesson when it gets corrected?** If not, it's one incident away from breaking trust.

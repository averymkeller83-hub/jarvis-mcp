# Jarvis MCP

**An AI assistant that unifies Claude's intelligence with OS control, proactive tool discovery, and self-improvement — all in one conversation.**

> *"What if Siri had Claude's brain, went hunting for tools you didn't know existed, and never made the same mistake twice?"*

Free with any Claude subscription. Powered by Claude.

---

## What This Is

An MCP server for Claude Desktop that turns Claude into a full AI assistant with four pillars:

| Pillar | What It Does |
|---|---|
| **Brains** | Claude does the thinking — chat, reasoning, code, research, screen reading. Routes casual chat through Groq (free) by default, or your Claude sub if you prefer. |
| **Hands** | Siri-style OS control — messages, calls, reminders, alarms, music, HomeKit, calendar. Works with Apple, Google Workspace, and Microsoft 365. |
| **Scout** | Proactive discovery — finds MCP servers, plugins, and tools tailored to your stack. Sandbox-tests them before showing you. One-click install. |
| **Lessons** | Self-improvement — learns from every correction, never repeats the same mistake. You approve every lesson before it's saved. |

**One conversation. No mode switching.** You talk, the assistant figures out whether to think, act, discover, or remember — and handles it behind the scenes.

## Quick Install

```bash
brew install --cask jarvis-mcp
```

First-run setup walks you through 12 steps (all skippable except welcome + Claude connection). Takes under 10 minutes.

## What You Need

- macOS (Apple Silicon recommended)
- [Claude Desktop](https://claude.ai/download) with any subscription (Free, Pro, or Max)
- That's it. Everything else is optional.

## Architecture

```
Claude Desktop (your subscription)
        │ MCP over stdio
        ▼
Jarvis MCP Extension (always works alone)
  • Smart router    • Unified memory
  • Screen reading  • Lessons read
  • Workspace search
        │ HTTPS auto-discover (127.0.0.1:7900)
        ▼
Jarvis Core Daemon (optional upgrade)
  • FastAPI server    • Voice pipeline
  • Scout agent       • Briefings
  • OS integrations   • Lessons write
  • CONTROL actions
```

**Progressive enhancement:** The extension works standalone. Installing the optional Core daemon unlocks Hands, Scout, Lessons write, voice, and briefings. Each tier is a clean upgrade.

## Features

### Unified Chat
Everything happens in one conversation. Ask a question, refactor code, text someone, check your calendar, discover a new tool — all in the same thread. The router silently picks the right handler.

### Voice
- **Listen:** Whisper.cpp (local, private) with cloud fallback
- **Speak:** Fish Audio TTS with local phrase cache (instant on common phrases)
- **Activate:** `⌥Space` hotkey or optional on-device wake word

### Morning Briefing
8-section daily briefing delivered to Obsidian + Telegram + voice:
Weather → Calendar → Email → GitHub → News → Reminders → Scout Discover → Lessons Digest

Empty sections are silently skipped. Light day = short briefing.

### Services
Supports Apple, Google Workspace, and Microsoft 365 simultaneously. Smart routing by contact — if David is in your Google Contacts, email goes through Gmail automatically.

### Privacy
- All data stays on your machine by default
- Voice audio processed locally (cloud fallback only on low confidence)
- Scout sources are opt-in — nothing scans until you say so
- Optional anonymous telemetry (off by default, fully transparent)
- One-command uninstall exports your data before removing everything

## Personalization

- Name the assistant anything you want
- Pick what it calls you
- Choose your voice profile
- Configure notification routing per event type
- Move CONTROL actions between instant-fire and confirm-first tiers
- All settings available via menubar, web dashboard, or config files

## Coming in v1.5: Agent Orchestration + Mission Control

The next phase adds the Claude Agent SDK to turn single-shot commands into autonomous multi-step workflows:

- **Multi-step chains** — "Research competitors, draft a summary email, and text me when it's done" runs autonomously across Brains, Hands, and Lessons
- **Persistent background agents** — "Monitor my CI and ping me if anything breaks" survives across sessions
- **Mission Control dashboard** — real-time visual monitoring of every active agent: what it's working on, what step it's on, results as they come in
- **Web-accessible Mission Control** — check on your agents from your phone, not just your Mac

## Project Structure

```
src/
  brain/       # Router, classification, model routing
  hands/       # CONTROL surface, AppleScript, OS integrations
  scout/       # Source scanning, sandbox testing, scoring, cards
  lessons/     # Capture, approval, retrieval, pruning
  voice/       # STT (Whisper), TTS (Fish Audio), activation
  briefing/    # Composer, Obsidian writer, delivery
  engine/      # Proactive scheduler, background tasks, notifications
  setup/       # 12-step first-run setup flow
  settings/    # Settings manager, web dashboard, TOML config
  integrations/  # Weather, RSS, GitHub, Apple/Google/Microsoft connectors
config/        # Example TOML configs (user copies and customizes)
docs/specs/    # Locked v1 spec (550+ lines, 30+ decisions)
tests/         # Test suite (538+ tests)
scripts/       # Utility scripts
```

## Status

**v1 spec is locked.** Implementation in progress — 538 tests passing across all pillars. See [`docs/specs/2026-04-15-jarvis-v1-north-star.md`](docs/specs/2026-04-15-jarvis-v1-north-star.md) for the complete spec.

### Roadmap

| Phase | Scope | Status |
|---|---|---|
| v1 — Mac Core | Extension + daemon + Hands + Scout + Lessons + voice + briefings | Building |
| v1.5 — Agent Orchestration | Claude Agent SDK integration + Mission Control dashboard — multi-step agent chains, persistent background agents, live visual monitoring of agent status/progress/results | Planned |
| v2 — Phone Reach | "Hey Siri, Jarvis..." + relay server + AirPods + CarPlay + web-accessible Mission Control | Planned |
| v3 — Native iOS | iOS app + Watch + tap-to-talk + team/multi-user features | Planned |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

*Powered by [Claude](https://claude.ai) by Anthropic.*

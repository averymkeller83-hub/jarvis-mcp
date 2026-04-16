# Contributing to Jarvis MCP

Thanks for your interest in contributing.

## Getting Started

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Read the v1 spec at `docs/specs/2026-04-15-jarvis-v1-north-star.md` — every feature decision is documented there
4. Make your changes
5. Run tests (`pytest`)
6. Commit with a clear message
7. Open a PR

## Ground Rules

- **Read the spec first.** Every design decision has been made and documented. If your PR conflicts with the spec, reference which decision you're proposing to change and why.
- **One PR, one thing.** Don't bundle unrelated changes.
- **Tests required.** New features need tests. Bug fixes need regression tests.
- **No walls of text in PRs.** Short description, what changed, how to test it.

## Architecture

The project follows four pillars — every feature belongs to exactly one:

1. **Brains** — Claude intelligence, routing, model selection
2. **Hands** — OS control, CONTROL surface, service integrations
3. **Scout** — Proactive discovery, sandbox testing, one-click install
4. **Lessons** — Self-improvement, correction capture, lesson retrieval

If your feature doesn't fit a pillar, open an issue to discuss before building.

## Code Style

- Python 3.12+
- Type hints on all public functions
- `pytest` for testing
- Keep files under 500 lines
- Prefer small, focused modules over large files

## Reporting Issues

- Check existing issues first
- Include: what you expected, what happened, steps to reproduce
- For feature requests: which pillar does it serve?

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.

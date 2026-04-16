# Mission Control Dashboard — Design Spec

**Date:** 2026-04-16
**Status:** Approved
**Author:** Avery Keller + JARVIS

## Overview

Mission Control is a web dashboard for monitoring and managing Jarvis. It provides at-a-glance system health, agent management, briefing viewing, scout discovery, settings configuration, activity logs, and first-run onboarding — all behind JWT authentication and designed for multi-user readiness.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Audience | Multi-user ready | Auth, user-scoped data, future-proofed |
| Frontend | React SPA (Vite + TypeScript) | Clean separation from Python backend, component model |
| Auth | JWT (access + refresh tokens) | Standard for SPAs, stateless, FastAPI-friendly |
| Visual style | Slate Professional | Dark slate (#0f172a), blue accents (#3b82f6), muted tones |
| Architecture | Monorepo with embedded frontend | Single repo, FastAPI serves built assets, zero CORS in prod |
| E2E testing | Deferred to v2 | Manual testing sufficient for v1 |

---

## 1. Project Structure & Dev Setup

```
jarvis-mcp/
├── dashboard/                  # React SPA
│   ├── src/
│   │   ├── api/               # API client (typed fetch wrappers)
│   │   ├── components/        # Shared UI components
│   │   ├── hooks/             # Custom hooks (useAuth, useAgents, usePolling)
│   │   ├── pages/             # One file per route
│   │   ├── stores/            # Auth state (React context)
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── vite.config.ts         # Proxy /api/* → localhost:7900
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
├── src/server/app.py          # FastAPI — serves dashboard/dist/ + API
└── ...
```

**Stack:** Vite + React 18 + TypeScript + Tailwind CSS + React Router v6

**Dev mode:** `npm run dev` starts Vite on `:5173`, proxies all `/api/*` requests to FastAPI at `:7900`.

**Production:** `npm run build` outputs to `dashboard/dist/`. FastAPI mounts it as static files and serves `index.html` for all non-API routes (SPA fallback).

**API prefix:** All backend endpoints get prefixed under `/api/` (e.g. `/api/agents`, `/api/status`). Existing unprefixed routes remain as aliases for backward compatibility (Telegram bot, LaunchAgent).

---

## 2. Authentication

### Backend — `src/auth/`

- **`models.py`** — User model stored in `config/users.toml` (username, hashed password with bcrypt, role: admin/user). First registered user becomes admin.
- **`jwt.py`** — `create_token()` and `verify_token()`. Access tokens (15 min TTL) + refresh tokens (7 day TTL). Secret key stored in `config/auth_secret.toml` (auto-generated on first run).

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Create account (rate-limited) |
| POST | `/api/auth/login` | No | Returns `{access_token, refresh_token}` |
| POST | `/api/auth/refresh` | No | Swap refresh token for new access token |
| GET | `/api/auth/me` | Yes | Returns current user info |

### Protection

FastAPI dependency `get_current_user()` injected into all `/api/*` routes except `/api/auth/*` and `/api/health`. Returns 401 if token is missing or expired.

### Frontend

Auth store holds tokens in `localStorage`. API client auto-attaches `Authorization: Bearer <token>` header. On 401 response, attempts refresh; if refresh fails, redirects to login page.

---

## 3. Pages & Routing

Seven routes, all behind auth (except `/login` and `/setup`):

| Route | Page | Description |
|---|---|---|
| `/` | Dashboard Home | Service health grid, agent summary (running/pending/error counts), uptime, quick-action buttons (trigger briefing, run scout) |
| `/agents` | Agents | Table of all agents — name, status badge, permissions, schedule. Click row → detail panel with context data, start/stop/approve buttons, manual invoke |
| `/briefing` | Briefing Viewer | Today's briefing rendered as cards per section. "Compose Now" button. Past briefings browsable if Obsidian export is enabled (reads from `briefings/` directory); otherwise shows current only |
| `/scout` | Scout | Recent discoveries as cards with relevance score. Install/dismiss buttons. "Scan Now" trigger. Source toggle list |
| `/settings` | Settings | React port of the existing settings dashboard — personality, voice, behavior, communication, news sources, notifications, privacy |
| `/activity` | Logs/Activity | Live event feed from EventBus (poll every 5s). Filterable by source agent. Shows event name, timestamp, payload preview |
| `/setup` | Setup Wizard | Step-by-step onboarding (13 steps). Progress bar, one step per screen |

### Navigation

Left sidebar with icon + label for each page. Collapsible on mobile. User avatar + logout at the bottom.

### Routing

React Router v6. `ProtectedRoute` wrapper redirects to `/login` if no token. `/setup` is accessible without auth (it creates the first user).

### Data Fetching

Dashboard home and activity page poll every 5-10 seconds. Other pages fetch on mount. No WebSocket for v1.

---

## 4. Component Library & Styling

### Shared Components

| Component | Description |
|---|---|
| `StatusBadge` | Colored pill — green (running), yellow (pending), red (error), gray (stopped) |
| `Card` | Slate surface with border, rounded corners. Base building block. |
| `StatCard` | Card variant with label/value/subtitle for dashboard grid |
| `DataTable` | Sortable rows, clickable for detail expansion |
| `Toggle` | On/off switch for settings booleans |
| `SidebarLayout` | Left nav + main content area. All pages wrapped in this. |
| `Modal` | Slide-over panel for detail views and confirmation dialogs |
| `Toast` | Success/error notifications, bottom-right, auto-dismiss |
| `ProtectedRoute` | Auth gate — redirects to login if no token |

### Design Tokens (Tailwind Config)

| Token | Value | Usage |
|---|---|---|
| `bg-primary` | `#0f172a` | Page background |
| `bg-card` | `#1e293b` | Card surfaces |
| `border-default` | `#334155` | Card/table borders |
| `accent` | `#3b82f6` | Buttons, links, active states |
| `text-primary` | `#f8fafc` | Headings, values |
| `text-secondary` | `#94a3b8` | Labels, subtitles |
| `success` | `#22c55e` | Running, healthy |
| `warning` | `#eab308` | Pending |
| `danger` | `#ef4444` | Error, stopped |

No external component library. Tailwind utility classes + custom components. Small bundle, consistent style.

---

## 5. API Client & Backend Changes

### Frontend API Client

- `dashboard/src/api/client.ts` — base client with JWT auto-attach, 401 refresh handling, typed errors
- One file per domain: `auth.ts`, `agents.ts`, `briefing.ts`, `scout.ts`, `settings.ts`, `engine.ts`, `setup.ts`, `events.ts`
- TypeScript interfaces mirror backend response shapes

### Backend Changes

1. **API prefix migration** — `APIRouter` with `prefix="/api"` for all existing endpoints. Legacy unprefixed routes kept as aliases for backward compatibility.

2. **Auth module** — New `src/auth/` package: `models.py`, `jwt.py`, `dependencies.py`. Endpoints under `/api/auth/`.

3. **Static file serving** — Mount `dashboard/dist/` at `/`. API routes checked first, then static files, then SPA fallback to `index.html`.

4. **CORS update** — Add `localhost:5173` to allowed origins for Vite dev server.

5. **Event history endpoint** — `GET /api/events/history` returns last N events from an in-memory ring buffer (200 events max) on the EventBus. Filterable by `?source=agentname`. The existing `/events` endpoint (subscription list) is unchanged.

No changes to existing endpoint behavior. All changes are additive.

---

## 6. Testing Strategy

### Backend (pytest)

- **Auth tests** (`tests/test_auth.py`): registration, login, token refresh, expired token rejection, protected route enforcement, first-user-is-admin
- **API prefix tests**: spot-check `/api/agents` and `/api/status` return same data as legacy paths
- **Event history tests**: ring buffer stores events, respects size limit, filters by source

### Frontend (Vitest + React Testing Library)

- **API client**: mock fetch, verify auth header, 401 refresh flow
- **Components**: StatusBadge colors, DataTable sorting, ProtectedRoute redirect
- **Page smoke tests**: each page renders without crash given mocked API data
- Located in `dashboard/src/__tests__/`

### E2E — deferred to v2

Manual testing against dev server is sufficient for v1.

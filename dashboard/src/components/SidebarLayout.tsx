import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { usePersonality } from "../stores/personality";
import { ErrorBoundary } from "./ErrorBoundary";

function IconDashboard() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="7" height="7" rx="1.5" />
      <rect x="11" y="2" width="7" height="4" rx="1.5" />
      <rect x="11" y="8" width="7" height="10" rx="1.5" />
      <rect x="2" y="11" width="7" height="7" rx="1.5" />
    </svg>
  );
}

function IconChat() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 4.5A1.5 1.5 0 014.5 3h11A1.5 1.5 0 0117 4.5v8a1.5 1.5 0 01-1.5 1.5H7l-4 3v-3 " />
      <circle cx="7" cy="8.5" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="10" cy="8.5" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="13" cy="8.5" r="0.75" fill="currentColor" stroke="none" />
    </svg>
  );
}

function IconAgents() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="6" r="3" />
      <path d="M4 16c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <circle cx="16" cy="5" r="2" />
      <path d="M18 12a4 4 0 00-4-4" />
    </svg>
  );
}

function IconBriefing() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="2" width="14" height="16" rx="2" />
      <path d="M7 6h6M7 9.5h6M7 13h3" />
    </svg>
  );
}

function IconScout() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="M14 14l4 4" />
      <path d="M8.5 5.5v3l2 1.5" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="10" cy="10" r="2.5" />
      <path d="M10 2v2.5M10 15.5V18M18 10h-2.5M4.5 10H2M15.66 4.34l-1.77 1.77M6.11 13.89l-1.77 1.77M15.66 15.66l-1.77-1.77M6.11 6.11L4.34 4.34" />
    </svg>
  );
}

function IconActivity() {
  return (
    <svg className="w-[18px] h-[18px]" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 10h3l2-5 3 10 2-5h6" />
    </svg>
  );
}

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: <IconDashboard /> },
  { to: "/chat", label: "Chat", icon: <IconChat /> },
  { to: "/agents", label: "Agents", icon: <IconAgents /> },
  { to: "/briefing", label: "Briefing", icon: <IconBriefing /> },
  { to: "/scout", label: "Scout", icon: <IconScout /> },
  { to: "/activity", label: "Activity", icon: <IconActivity /> },
  { to: "/settings", label: "Settings", icon: <IconSettings /> },
];

interface Props {
  children: ReactNode;
}

function JarvisMark() {
  return (
    <svg className="w-7 h-7" viewBox="0 0 32 32" fill="none">
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

export function SidebarLayout({ children }: Props) {
  const { user, logout } = useAuth();
  const { assistantName } = usePersonality();
  const [mobileOpen, setMobileOpen] = useState(false);

  function handleNavClick() {
    setMobileOpen(false);
  }

  return (
    <div className="flex min-h-screen bg-void">
      {/* Mobile header */}
      <div className="fixed top-0 left-0 right-0 z-30 flex items-center justify-between glass border-b border-border-subtle px-4 py-3 md:hidden">
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="text-text-primary p-1.5 rounded-lg hover:bg-surface transition-colors"
          aria-label="Toggle menu"
        >
          {mobileOpen ? (
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h6a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
            </svg>
          )}
        </button>
        <div className="flex items-center gap-2">
          <JarvisMark />
          <span className="text-text-primary font-display font-semibold text-sm">
            {assistantName}
          </span>
        </div>
        <div className="w-8" />
      </div>

      {/* Overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-void/60 backdrop-blur-xs z-30 md:hidden animate-fade-in"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <nav
        className={`
          fixed md:sticky top-0 left-0 h-screen w-60 flex-shrink-0
          border-r border-border-subtle flex flex-col
          bg-primary/95 backdrop-blur-sm z-40
          transition-transform duration-250 ease-out
          ${mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
        `}
      >
        {/* Logo */}
        <div className="p-5 border-b border-border-subtle">
          <div className="flex items-center gap-3">
            <JarvisMark />
            <div>
              <span className="text-text-primary font-display font-bold text-sm tracking-wide block">
                {assistantName}
              </span>
              <span className="text-text-muted text-[10px] font-mono uppercase tracking-widest">
                Mission Control
              </span>
            </div>
          </div>
        </div>

        {/* Nav */}
        <div className="flex-1 py-3 overflow-y-auto">
          <div className="px-3 mb-1">
            <p className="section-title px-2 mb-2">Navigation</p>
          </div>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              onClick={handleNavClick}
              className={({ isActive }) =>
                `flex items-center gap-3 mx-2 px-3 py-2 rounded-lg text-sm font-body
                 transition-all duration-150
                 ${isActive
                   ? "text-accent bg-accent-muted border border-accent/15"
                   : "text-text-secondary hover:text-text-primary hover:bg-surface border border-transparent"
                 }`
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </div>

        {/* User */}
        {user && (
          <div className="p-4 border-t border-border-subtle">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent-muted flex items-center justify-center">
                <span className="text-accent text-xs font-bold font-display">
                  {user.username.charAt(0).toUpperCase()}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-text-primary font-medium truncate">
                  {user.username}
                </p>
                <button
                  onClick={logout}
                  className="text-[11px] text-text-muted hover:text-danger transition-colors"
                >
                  Sign out
                </button>
              </div>
            </div>
          </div>
        )}
      </nav>

      {/* Main content */}
      <main className="flex-1 pt-14 md:pt-0 overflow-y-auto min-w-0">
        <div className="page-container p-4 md:p-8">
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </div>
      </main>
    </div>
  );
}

import { NavLink } from "react-router-dom";
import { useAuth } from "../stores/auth";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "◉" },
  { to: "/agents", label: "Agents", icon: "⬡" },
  { to: "/briefing", label: "Briefing", icon: "◈" },
  { to: "/scout", label: "Scout", icon: "◎" },
  { to: "/settings", label: "Settings", icon: "⚙" },
  { to: "/activity", label: "Activity", icon: "▤" },
];

interface Props {
  children: React.ReactNode;
}

export function SidebarLayout({ children }: Props) {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-primary">
      {/* Sidebar */}
      <nav className="w-56 flex-shrink-0 border-r border-border-default flex flex-col">
        <div className="p-5 border-b border-border-default">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-accent" />
            <span className="text-text-primary font-semibold">
              Mission Control
            </span>
          </div>
        </div>

        <div className="flex-1 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm transition-colors ${
                  isActive
                    ? "text-accent bg-accent/10 border-r-2 border-accent"
                    : "text-text-secondary hover:text-text-primary hover:bg-white/5"
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </div>

        {user && (
          <div className="p-4 border-t border-border-default">
            <p className="text-sm text-text-primary mb-1">{user.username}</p>
            <button
              onClick={logout}
              className="text-xs text-text-secondary hover:text-danger transition-colors"
            >
              Sign out
            </button>
          </div>
        )}
      </nav>

      {/* Main content */}
      <main className="flex-1 p-8 overflow-y-auto">{children}</main>
    </div>
  );
}

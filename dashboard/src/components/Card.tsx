import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  hover?: boolean;
}

export function Card({ children, className = "", hover }: CardProps) {
  return (
    <div
      className={`card ${hover ? "glass-hover cursor-pointer" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  status?: "online" | "warning" | "error" | "offline";
  icon?: ReactNode;
}

export function StatCard({ label, value, subtitle, status, icon }: StatCardProps) {
  const dotClass = status
    ? `status-dot-${status}`
    : "";

  return (
    <Card className="group relative overflow-hidden">
      <div className="flex items-start justify-between mb-3">
        <p className="section-title flex items-center gap-2">
          {status && <span className={dotClass} />}
          {label}
        </p>
        {icon && (
          <span className="text-text-muted group-hover:text-accent transition-colors duration-200">
            {icon}
          </span>
        )}
      </div>
      <p className="data-value">{value}</p>
      {subtitle && (
        <p className="text-text-secondary text-xs mt-1.5 font-body">{subtitle}</p>
      )}
    </Card>
  );
}

export function LoadingCard() {
  return (
    <div className="card">
      <div className="space-y-3">
        <div className="h-3 w-20 rounded bg-border-subtle loading-shimmer" />
        <div className="h-7 w-16 rounded bg-border-subtle loading-shimmer" />
        <div className="h-3 w-32 rounded bg-border-subtle loading-shimmer" />
      </div>
    </div>
  );
}

import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <div
      className={`bg-card border border-border-default rounded-xl p-5 ${className}`}
    >
      {children}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
}

export function StatCard({ label, value, subtitle }: StatCardProps) {
  return (
    <Card>
      <p className="text-text-secondary text-xs uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className="text-text-primary text-2xl font-bold">{value}</p>
      {subtitle && (
        <p className="text-text-secondary text-xs mt-1">{subtitle}</p>
      )}
    </Card>
  );
}

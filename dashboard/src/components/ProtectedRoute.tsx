import { useState, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { fetchSetupStatus } from "../api/setup";

interface Props {
  children: React.ReactNode;
}

function LoadingScreen() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-void">
      <div className="flex flex-col items-center gap-4">
        <svg className="w-10 h-10 animate-pulse-glow" viewBox="0 0 32 32" fill="none">
          <circle cx="16" cy="16" r="14" stroke="currentColor" strokeWidth="1.2" className="text-border-default" />
          <circle cx="16" cy="16" r="8" stroke="currentColor" strokeWidth="1" className="text-accent/60" />
          <circle cx="16" cy="16" r="3" fill="currentColor" className="text-accent" />
        </svg>
        <p className="text-text-muted text-sm font-mono tracking-wider uppercase">
          Initializing
        </p>
      </div>
    </div>
  );
}

export function ProtectedRoute({ children }: Props) {
  const { user, loading } = useAuth();
  const [setupDone, setSetupDone] = useState<boolean | null>(null);

  useEffect(() => {
    fetchSetupStatus()
      .then((s) => setSetupDone(s.setup_complete))
      .catch(() => setSetupDone(false));
  }, []);

  if (loading || setupDone === null) {
    return <LoadingScreen />;
  }

  if (!setupDone) {
    return <Navigate to="/setup" replace />;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

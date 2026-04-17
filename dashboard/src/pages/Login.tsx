import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { checkClaudeDesktop, loginWithClaudeDesktop } from "../api/auth";
import { useAuth } from "../stores/auth";
import { usePersonality } from "../stores/personality";

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

type Status = "checking" | "connecting" | "not_running" | "not_signed_in" | "error";

export function Login() {
  const [status, setStatus] = useState<Status>("checking");
  const [errorMsg, setErrorMsg] = useState("");
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const { assistantName } = usePersonality();

  const attemptLogin = useCallback(async () => {
    setStatus("checking");
    setErrorMsg("");
    try {
      const cdStatus = await checkClaudeDesktop();
      if (!cdStatus.running) {
        setStatus("not_running");
        return;
      }
      if (!cdStatus.authenticated) {
        setStatus("not_signed_in");
        return;
      }

      setStatus("connecting");
      await loginWithClaudeDesktop();
      await refresh();
      navigate("/");
    } catch {
      setErrorMsg("Could not connect to Claude Desktop");
      setStatus("error");
    }
  }, [refresh, navigate]);

  useEffect(() => {
    attemptLogin();
  }, [attemptLogin]);

  const isPulsing = status === "checking" || status === "connecting";

  return (
    <div className="min-h-screen bg-void flex items-center justify-center px-4">
      {/* Subtle radial glow behind the card */}
      <div className="fixed inset-0 pointer-events-none bg-page-gradient" />

      <div className="relative w-full max-w-sm animate-slide-up">
        {/* Logo + Branding */}
        <div className="flex flex-col items-center mb-10">
          <div className={`mb-4 ${isPulsing ? "animate-pulse-glow" : ""} rounded-full`}>
            <JarvisMark size={56} />
          </div>
          <h1 className="text-2xl font-bold text-text-primary font-display tracking-tight">
            {assistantName} Mission Control
          </h1>
          <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-text-muted mt-1.5">
            Mission Control
          </p>
        </div>

        {/* Status Card */}
        <div className="card animate-fade-in">
          {status === "checking" && (
            <div className="text-center py-3">
              <div className="w-14 h-14 rounded-full bg-accent-muted flex items-center justify-center mx-auto mb-4 animate-pulse-glow">
                <div className="w-5 h-5 rounded-full bg-accent animate-pulse" />
              </div>
              <p className="text-text-primary font-semibold font-display text-lg">
                Detecting Claude Desktop
              </p>
              <p className="text-text-secondary text-sm mt-1.5 font-body">
                Checking for an active Claude session
              </p>
            </div>
          )}

          {status === "connecting" && (
            <div className="text-center py-3">
              <div className="w-14 h-14 rounded-full bg-success-muted flex items-center justify-center mx-auto mb-4 animate-pulse-glow">
                <div className="w-5 h-5 rounded-full bg-success animate-pulse" />
              </div>
              <p className="text-text-primary font-semibold font-display text-lg">
                Claude Desktop Found
              </p>
              <p className="text-text-secondary text-sm mt-1.5 font-body">
                Signing you in...
              </p>
            </div>
          )}

          {status === "not_running" && (
            <div className="text-center py-3">
              <div className="w-14 h-14 rounded-full bg-warning-muted flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <p className="text-text-primary font-semibold font-display text-lg mb-1">
                Claude Desktop Not Running
              </p>
              <p className="text-text-secondary text-sm mb-6 font-body">
                Open Claude Desktop and sign into your account, then come back here.
              </p>
              <button onClick={attemptLogin} className="btn-primary w-full">
                Try Again
              </button>
            </div>
          )}

          {status === "not_signed_in" && (
            <div className="text-center py-3">
              <div className="w-14 h-14 rounded-full bg-warning-muted flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                </svg>
              </div>
              <p className="text-text-primary font-semibold font-display text-lg mb-1">
                Not Signed In
              </p>
              <p className="text-text-secondary text-sm mb-6 font-body">
                Claude Desktop is open but you're not signed in. Sign into your Claude account, then come back here.
              </p>
              <button onClick={attemptLogin} className="btn-primary w-full">
                Try Again
              </button>
            </div>
          )}

          {status === "error" && (
            <div className="text-center py-3">
              <div className="w-14 h-14 rounded-full bg-danger-muted flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <p className="text-text-primary font-semibold font-display text-lg mb-1">
                Connection Failed
              </p>
              <p className="text-text-secondary text-sm mb-6 font-body">{errorMsg}</p>
              <button onClick={attemptLogin} className="btn-primary w-full">
                Retry
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-text-muted text-xs font-mono mt-6 tracking-wide">
          v1.0 &middot; Authenticated via Claude Desktop
        </p>
      </div>
    </div>
  );
}

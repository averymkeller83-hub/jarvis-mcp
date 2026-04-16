import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { login, register } from "../api/auth";
import { useAuth } from "../stores/auth";
import { ApiError } from "../api/client";

export function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const { refresh } = useAuth();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isRegister) {
        await register(username, password);
      }
      await login(username, password);
      await refresh();
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Something went wrong");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-primary flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-2.5 h-2.5 rounded-full bg-accent" />
          <h1 className="text-xl font-semibold text-text-primary">
            Mission Control
          </h1>
        </div>

        <div className="bg-card border border-border-default rounded-xl p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            {isRegister ? "Create Account" : "Sign In"}
          </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
                required
              />
            </div>

            {error && (
              <p className="text-danger text-sm">{error}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-accent hover:bg-accent-hover text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {submitting
                ? "..."
                : isRegister
                  ? "Create Account"
                  : "Sign In"}
            </button>
          </form>

          <button
            onClick={() => setIsRegister(!isRegister)}
            className="mt-4 text-sm text-text-secondary hover:text-accent transition-colors w-full text-center"
          >
            {isRegister
              ? "Already have an account? Sign in"
              : "Need an account? Register"}
          </button>
        </div>
      </div>
    </div>
  );
}

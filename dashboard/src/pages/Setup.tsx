import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { useToast } from "../components/Toast";
import { startSetup, submitStep, skipStep } from "../api/setup";
import { register, login } from "../api/auth";
import { useAuth } from "../stores/auth";

export function Setup() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [step, setStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(13);
  const [config, setConfig] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    startSetup()
      .then((progress) => {
        setStep(progress.current_step);
        setTotalSteps(progress.total_steps);
      })
      .catch(() => {});
  }, []);

  async function handleNext() {
    setLoading(true);
    try {
      const result = await submitStep(step, config);
      if (result.complete) {
        if (config.username && config.password) {
          await register(config.username, config.password);
          await login(config.username, config.password);
          await refresh();
        }
        toast("Setup complete!");
        navigate("/");
        return;
      }
      setStep((result.current_step as number) ?? step + 1);
      setConfig({});
    } catch {
      toast("Step failed", "error");
    } finally {
      setLoading(false);
    }
  }

  async function handleSkip() {
    try {
      const result = await skipStep(step);
      setStep((result.current_step as number) ?? step + 1);
      setConfig({});
    } catch {
      toast("Cannot skip this step", "error");
    }
  }

  const pct = totalSteps > 0 ? Math.round((step / totalSteps) * 100) : 0;

  return (
    <div className="min-h-screen bg-primary flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-2 mb-8 justify-center">
          <div className="w-2.5 h-2.5 rounded-full bg-accent" />
          <h1 className="text-xl font-semibold text-text-primary">
            Jarvis Setup
          </h1>
        </div>

        <div className="mb-6">
          <div className="flex justify-between text-xs text-text-secondary mb-1">
            <span>
              Step {step} of {totalSteps}
            </span>
            <span>{pct}%</span>
          </div>
          <div className="h-1.5 bg-card rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        <Card>
          <h2 className="text-lg font-semibold text-text-primary mb-4">
            Step {step}
          </h2>
          <p className="text-text-secondary text-sm mb-6">
            Configure this step's settings below.
          </p>

          <div className="space-y-3 mb-6">
            <div>
              <label className="block text-sm text-text-secondary mb-1">
                Value
              </label>
              <input
                type="text"
                value={config.value ?? ""}
                onChange={(e) =>
                  setConfig((prev) => ({ ...prev, value: e.target.value }))
                }
                className="w-full bg-primary border border-border-default rounded-lg px-3 py-2 text-text-primary focus:border-accent focus:outline-none"
              />
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleNext}
              disabled={loading}
              className="flex-1 bg-accent hover:bg-accent-hover text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? "..." : step === totalSteps ? "Finish" : "Next"}
            </button>
            <button
              onClick={handleSkip}
              className="bg-card border border-border-default text-text-secondary px-4 py-2.5 rounded-lg hover:text-text-primary transition-colors"
            >
              Skip
            </button>
          </div>
        </Card>
      </div>
    </div>
  );
}

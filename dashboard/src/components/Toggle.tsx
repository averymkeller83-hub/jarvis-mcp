interface Props {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}

export function Toggle({ checked, onChange, label }: Props) {
  return (
    <label className="inline-flex items-center gap-2.5 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`
          relative w-11 h-6 rounded-full transition-all duration-200
          ${checked
            ? "bg-accent/30 border-accent/40"
            : "bg-surface border-border-default"
          }
          border
        `}
      >
        <span
          className={`
            absolute top-0.5 left-0.5 w-5 h-5 rounded-full
            transition-all duration-200
            ${checked
              ? "translate-x-5 bg-accent shadow-[0_0_8px_rgba(192,145,90,0.4)]"
              : "bg-text-secondary"
            }
          `}
        />
      </button>
      {label && <span className="text-sm text-text-secondary">{label}</span>}
    </label>
  );
}

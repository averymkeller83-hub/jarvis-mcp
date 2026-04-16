import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#0f172a",
        card: "#1e293b",
        "border-default": "#334155",
        accent: "#3b82f6",
        "accent-hover": "#2563eb",
        "text-primary": "#f8fafc",
        "text-secondary": "#94a3b8",
        success: "#22c55e",
        warning: "#eab308",
        danger: "#ef4444",
      },
    },
  },
  plugins: [],
} satisfies Config;

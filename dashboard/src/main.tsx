import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./main.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-text-secondary text-lg">Mission Control loading...</p>
    </div>
  </StrictMode>,
);

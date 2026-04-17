import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface Toast {
  id: number;
  message: string;
  type: "success" | "error";
}

interface ToastContextValue {
  toast: (message: string, type?: "success" | "error") => void;
}

const ToastContext = createContext<ToastContextValue>({
  toast: () => {},
});

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: "success" | "error" = "success") => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-5 right-5 flex flex-col gap-2 z-50">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`
              flex items-center gap-2.5 px-4 py-3 rounded-xl
              font-medium text-sm shadow-deep animate-slide-up
              border backdrop-blur-sm
              ${t.type === "success"
                ? "bg-success-muted border-success/20 text-success"
                : "bg-danger-muted border-danger/20 text-danger"
              }
            `}
          >
            <svg className="w-4 h-4 flex-shrink-0" viewBox="0 0 16 16" fill="currentColor">
              {t.type === "success" ? (
                <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm3.78-9.72a.75.75 0 00-1.06-1.06L7 8.94 5.28 7.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.06 0l4.25-4.25z" />
              ) : (
                <path d="M8 16A8 8 0 108 0a8 8 0 000 16zM5.354 5.354a.5.5 0 01.707 0L8 7.293l1.939-1.94a.5.5 0 01.707.708L8.707 8l1.94 1.939a.5.5 0 01-.708.707L8 8.707l-1.939 1.94a.5.5 0 01-.707-.708L7.293 8 5.354 6.061a.5.5 0 010-.707z" />
              )}
            </svg>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  return useContext(ToastContext);
}

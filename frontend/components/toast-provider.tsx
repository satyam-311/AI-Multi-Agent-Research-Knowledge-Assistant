"use client";

import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

type ToastVariant = "success" | "error" | "info";

type ToastItem = {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
};

type ToastInput = Omit<ToastItem, "id">;

type ToastContextValue = {
  toast: (input: ToastInput) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

function getToastStyles(variant: ToastVariant) {
  if (variant === "success") {
    return {
      icon: CheckCircle2,
      className:
        "border-emerald-500/20 bg-emerald-500/10 text-emerald-100 shadow-emerald-950/30",
    };
  }

  if (variant === "error") {
    return {
      icon: TriangleAlert,
      className:
        "border-rose-500/20 bg-rose-500/10 text-rose-100 shadow-rose-950/30",
    };
  }

  return {
    icon: Info,
    className:
      "border-cyan-500/20 bg-cyan-500/10 text-cyan-100 shadow-cyan-950/30",
  };
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = useCallback(
    ({ title, description, variant }: ToastInput) => {
      const id = crypto.randomUUID();
      setItems((current) => [...current, { id, title, description, variant }]);
      window.setTimeout(() => dismiss(id), 4200);
    },
    [dismiss]
  );

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-[70] flex w-[min(92vw,380px)] flex-col gap-3">
        {items.map((item) => {
          const styles = getToastStyles(item.variant);
          const Icon = styles.icon;

          return (
            <div
              key={item.id}
              className={`pointer-events-auto animate-slide-up rounded-3xl border p-4 shadow-2xl backdrop-blur-xl ${styles.className}`}
            >
              <div className="flex items-start gap-3">
                <span className="mt-0.5 rounded-2xl bg-black/20 p-2">
                  <Icon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">{item.title}</p>
                  {item.description && (
                    <p className="mt-1 text-sm text-current/80">{item.description}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  className="rounded-xl p-1 text-current/75 transition hover:bg-black/10 hover:text-current"
                  aria-label="Dismiss notification"
                >
                  <X size={15} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider.");
  }
  return context;
}

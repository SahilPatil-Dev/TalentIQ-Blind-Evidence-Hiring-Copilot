"use client";
/**
 * Toast.tsx — the little messages that slide up from the bottom
 * ("Candidate shortlisted", "Résumé evaluated", errors...).
 *
 * Wrap the app in <ToastProvider> once (done in layout.tsx), then in any
 * component:   const toast = useToast();   toast("success", "Saved!");
 */
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Icon } from "./Icon";

type Kind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: Kind;
  message: string;
}

const ToastContext = createContext<(kind: Kind, message: string) => void>(() => {});

/** Get the function that shows a toast. */
export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const show = useCallback((kind: Kind, message: string) => {
    const id = nextId.current++;
    setToasts((current) => [...current, { id, kind, message }]);
    // Remove it again after a few seconds.
    window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 3800);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.kind}`}>
            <Icon name={toast.kind === "error" ? "alert" : "check"} size={18} />
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

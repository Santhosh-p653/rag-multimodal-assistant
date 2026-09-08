import React, { useEffect } from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

export interface ToastMessage {
  id: string;
  type: "success" | "warning" | "info" | "error";
  title: string;
  description?: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

const ToastItem: React.FC<{ toast: ToastMessage; onDismiss: (id: string) => void }> = ({
  toast,
  onDismiss,
}) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss(toast.id);
    }, 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const getStyle = () => {
    switch (toast.type) {
      case "success":
        return {
          bg: "bg-emerald-50 border-emerald-200 text-emerald-800",
          icon: <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />,
        };
      case "warning":
        return {
          bg: "bg-amber-50 border-amber-200 text-amber-800",
          icon: <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />,
        };
      case "error":
        return {
          bg: "bg-red-50 border-red-200 text-red-800",
          icon: <AlertTriangle className="h-5 w-5 text-red-600 shrink-0" />,
        };
      default:
        return {
          bg: "bg-white border-octo-border text-octo-charcoal shadow-md",
          icon: <Info className="h-5 w-5 text-octo-orange shrink-0" />,
        };
    }
  };

  const style = getStyle();

  return (
    <div
      role="status"
      aria-live="polite"
      className={`pointer-events-auto p-4 rounded-card border text-xs flex items-start gap-3 shadow-md transition-all duration-200 animate-fadeIn ${style.bg}`}
    >
      {style.icon}
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm leading-tight">{toast.title}</p>
        {toast.description && <p className="mt-1 text-xs opacity-90 leading-relaxed">{toast.description}</p>}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="p-1 rounded hover:bg-black/5 opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss toast"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
};

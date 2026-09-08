import React, { Component, ErrorInfo, ReactNode } from "react";
import Link from "next/link";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(_: Error): State {
    return { hasError: true };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught Error Boundary Exception:", error, errorInfo);
  }

  public handleRetry = () => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#F7F4EE] text-[#252525] flex flex-col items-center justify-center p-6 text-center">
          <div className="max-w-md w-full octo-card p-8 flex flex-col items-center gap-4">
            <div className="p-4 bg-amber-50 rounded-full border border-amber-200 text-amber-700">
              <AlertTriangle className="h-8 w-8" />
            </div>

            <div className="space-y-1">
              <h1 className="text-xl font-bold tracking-tight">Something went wrong</h1>
              <p className="text-sm text-[#6F6A63] leading-relaxed">
                Octo RAG encountered an unexpected problem loading this view.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 w-full pt-2">
              <button
                onClick={this.handleRetry}
                className="flex-1 h-12 rounded-btn bg-[#C65D3A] text-white font-semibold text-sm flex items-center justify-center gap-2 hover:bg-[#B2502F] shadow-sm transition-all"
              >
                <RefreshCw className="h-4 w-4" />
                <span>Try again</span>
              </button>
              <Link
                href="/"
                onClick={() => this.setState({ hasError: false })}
                className="flex-1 h-12 rounded-btn bg-[#EFE9DF] border border-[#DED8CE] text-[#252525] font-semibold text-sm flex items-center justify-center gap-2 hover:bg-[#E4DCD0] transition-all"
              >
                <Home className="h-4 w-4" />
                <span>Go Home</span>
              </Link>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

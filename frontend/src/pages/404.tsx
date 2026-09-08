import Link from "next/link";
import { Compass, Home, ArrowLeft } from "lucide-react";

export default function Custom404() {
  return (
    <div className="min-h-screen bg-octo-bg text-octo-charcoal flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md w-full octo-card p-8 flex flex-col items-center gap-6 shadow-sm">
        <div className="p-4 bg-octo-orange-light rounded-full border border-octo-orange text-octo-orange">
          <Compass className="h-10 w-10 animate-pulse" />
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight text-octo-charcoal">
            Looks like this page wandered off.
          </h1>
          <p className="text-sm text-octo-muted leading-relaxed">
            Let's get you back to Octo RAG to answer your manual questions and troubleshoot equipment.
          </p>
        </div>

        <Link
          href="/"
          className="w-full h-12 rounded-btn bg-octo-orange text-white font-semibold text-sm flex items-center justify-center gap-2 hover:bg-octo-orange-hover shadow-sm transition-all"
        >
          <Home className="h-4 w-4" />
          <span>Back to Octo RAG</span>
        </Link>
      </div>
    </div>
  );
}

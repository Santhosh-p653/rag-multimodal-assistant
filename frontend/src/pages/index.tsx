import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Wrench,
  FileText,
  Trash2,
  AlertCircle,
  Volume2,
  VolumeX,
  Globe,
  SlidersHorizontal,
  RefreshCw,
  Type
} from "lucide-react";
import { ChatWindow } from "../components/ChatWindow";
import { ChatInput } from "../components/ChatInput";
import { AudioRecorder } from "../components/AudioRecorder";
import { Message } from "../components/MessageBubble";
import { ToastContainer, ToastMessage } from "../components/Toast";
import { sendMessage, fetchFiles, transcribeAudio } from "../lib/api";

interface HealthInfo {
  status: string;
  llm_provider: string;
  vectors_stored: number;
}

const LANG_NAMES: Record<string, string> = {
  auto: "Auto Detect",
  en: "English",
  hi: "हिंदी (Hindi)",
  ta: "தமிழ் (Tamil)",
  te: "తెలుగు (Telugu)",
  kn: "ಕನ್ನಡ (Kannada)",
  ml: "മലയാളം (Malayalam)",
  bn: "বাংলা (Bengali)",
  mr: "मराठी (Marathi)",
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(true);
  const [hintLang, setHintLang] = useState("auto");
  const [isTroubleshooting, setIsTroubleshooting] = useState(false);
  const [textSize, setTextSize] = useState<"standard" | "large" | "xl">("standard");
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = useCallback((type: ToastMessage["type"], title: string, description?: string) => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, type, title, description }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Offline / Reconnect Network Listener
  useEffect(() => {
    const handleOffline = () => {
      addToast("warning", "You're offline", "Check your internet connection.");
    };
    const handleOnline = () => {
      addToast("success", "Connection restored", "You are back online.");
    };

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, [addToast]);

  // Load saved text size preference
  useEffect(() => {
    const savedSize = localStorage.getItem("octo_text_size") as "standard" | "large" | "xl";
    if (savedSize && ["standard", "large", "xl"].includes(savedSize)) {
      setTextSize(savedSize);
    }
  }, []);

  const handleTextSizeChange = (newSize: "standard" | "large" | "xl") => {
    setTextSize(newSize);
    localStorage.setItem("octo_text_size", newSize);
  };

  // Check backend health on mount
  useEffect(() => {
    async function checkHealth() {
      try {
        const response = await fetch("http://localhost:8000/health");
        if (response.ok) {
          const data: HealthInfo = await response.json();
          setHealth(data);
          setBackendOnline(true);
          return;
        }
        setBackendOnline(false);
      } catch {
        setBackendOnline(false);
      }
    }
    checkHealth();
  }, []);

  // Fetch unique documents when backend becomes online
  useEffect(() => {
    async function loadFiles() {
      try {
        const fileList = await fetchFiles();
        setFiles(fileList);
      } catch (err) {
        console.error("Failed to load documents:", err);
      }
    }
    if (backendOnline) {
      loadFiles();
    }
  }, [backendOnline]);

  const handleSend = async (text: string) => {
    if (!text || !text.trim()) return;
    setErrorMessage(null);
    setLastQuery(text);

    const userMsg: Message = {
      id: Math.random().toString(36).substring(7),
      sender: "user",
      text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const data = await sendMessage(text, selectedFile);
      const assistantMsg: Message = {
        id: Math.random().toString(36).substring(7),
        sender: "assistant",
        text: data.answer,
        sources: data.sources,
        images: data.images,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const humanError = err.message || "Couldn't connect to the assistant server.";
      setErrorMessage(humanError);
      addToast("error", "Request Failed", humanError);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = () => {
    if (lastQuery) {
      addToast("info", "Retrying query...", lastQuery);
      handleSend(lastQuery);
    }
  };

  const handleAudioComplete = async (audioBlob: Blob) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await transcribeAudio(audioBlob, hintLang);
      if (data.text && data.text.trim()) {
        await handleSend(data.text);
      } else {
        const msg = "Speech was not recognized clearly. Please tap the microphone and try speaking again.";
        setErrorMessage(msg);
        addToast("warning", "Voice Recognition", msg);
      }
    } catch (err: any) {
      const humanError = err.message || "Failed to transcribe audio.";
      setErrorMessage(humanError);
      addToast("error", "Microphone Error", humanError);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLanguageChange = (newLang: string) => {
    setHintLang(newLang);
    const name = LANG_NAMES[newLang] || newLang;
    addToast("info", `Language set to ${name}`);
  };

  const clearChat = () => {
    setMessages([]);
    setErrorMessage(null);
    setLastQuery(null);
    setIsTroubleshooting(false);
  };

  const startGuidedTroubleshooting = () => {
    setIsTroubleshooting(true);
    handleSend("Help me troubleshoot and fix a problem with my machine step by step.");
  };

  return (
    <div className={`flex flex-col min-h-screen bg-octo-bg text-octo-charcoal size-${textSize}`}>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* ── Top Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-octo-border sticky top-0 z-30 shadow-sm">
        <div className="max-w-[1100px] mx-auto px-4 h-16 flex items-center justify-between">
          {/* Brand Name */}
          <div className="flex items-center gap-3">
            <Link href="/" onClick={clearChat} className="flex items-center gap-2 group">
              <span className="text-xl font-bold tracking-tight text-octo-charcoal">
                OCTO <span className="text-octo-orange">RAG</span>
              </span>
            </Link>

            {/* System Status Indicator */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-octo-surface-warm border border-octo-border text-octo-charcoal font-medium">
              <span className={`h-2 w-2 rounded-full ${backendOnline ? "bg-emerald-600" : "bg-amber-500 animate-pulse"}`} />
              <span>{backendOnline ? "System ready" : "Connecting..."}</span>
            </div>
          </div>

          {/* Top Controls */}
          <div className="flex items-center gap-2 sm:gap-4">
            {/* Document Manual Selector Filter */}
            {files.length > 0 && (
              <div className="hidden md:flex items-center gap-1.5 text-xs text-octo-muted">
                <SlidersHorizontal className="h-3.5 w-3.5 text-octo-orange" />
                <select
                  value={selectedFile || ""}
                  onChange={(e) => {
                    setSelectedFile(e.target.value || null);
                    if (e.target.value) addToast("info", "Filter applied", e.target.value);
                  }}
                  className="bg-octo-surface-warm border border-octo-border rounded-lg px-2.5 py-1 text-xs text-octo-charcoal font-medium focus:outline-none focus:border-octo-orange"
                >
                  <option value="">All Manuals</option>
                  {files.map((file) => (
                    <option key={file} value={file}>
                      📄 {file}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Accessibility Text Size Selector */}
            <div className="hidden sm:flex items-center gap-1 text-xs text-octo-muted border-l border-octo-border pl-3">
              <Type className="h-3.5 w-3.5 text-octo-muted" />
              <select
                value={textSize}
                onChange={(e) => handleTextSizeChange(e.target.value as any)}
                className="bg-transparent border-none text-xs text-octo-charcoal font-medium focus:outline-none cursor-pointer"
                title="Adjust font readability size"
              >
                <option value="standard">A Standard</option>
                <option value="large">A+ Large</option>
                <option value="xl">A++ Extra Large</option>
              </select>
            </div>

            {/* Language Selector */}
            <div className="flex items-center gap-1 text-xs text-octo-muted border-l border-octo-border pl-3">
              <Globe className="h-3.5 w-3.5 text-octo-muted hidden sm:inline" />
              <select
                value={hintLang}
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="bg-transparent border-none text-xs text-octo-charcoal font-medium focus:outline-none cursor-pointer"
              >
                <option value="auto">🌐 Auto Detect Language</option>
                <option value="en">English (en-IN)</option>
                <option value="hi">हिंदी (Hindi)</option>
                <option value="ta">தமிழ் (Tamil)</option>
                <option value="te">తెలుగు (Telugu)</option>
                <option value="kn">ಕನ್ನಡ (Kannada)</option>
                <option value="ml">മലയാളം (Malayalam)</option>
                <option value="bn">বাংলা (Bengali)</option>
                <option value="mr">मराठी (Marathi)</option>
              </select>
            </div>

            {/* Auto Read Aloud Toggle */}
            <button
              onClick={() => setIsMuted(!isMuted)}
              className={`p-2 rounded-lg border transition-colors ${
                !isMuted
                  ? "bg-octo-orange-light border-octo-orange text-octo-orange"
                  : "bg-white border-octo-border text-octo-muted hover:text-octo-charcoal"
              }`}
              title={isMuted ? "Enable auto-read answers" : "Disable auto-read answers"}
            >
              {!isMuted ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </button>

            {/* Link to Admin / Manuals Portal */}
            <Link
              href="/admin"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-btn bg-white border border-octo-border text-xs font-semibold text-octo-charcoal hover:bg-octo-surface-warm transition-colors shadow-sm"
            >
              <FileText className="h-4 w-4 text-octo-orange" />
              <span className="hidden sm:inline">My Manuals</span>
            </Link>
          </div>
        </div>
      </header>

      {/* ── Main Content Body ─────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col max-w-[1100px] w-full mx-auto p-4 md:p-6">
        {/* Human-Readable Error Recovery Alert */}
        {errorMessage && (
          <div className="mb-4 p-4 rounded-card bg-red-50 border border-red-200 text-red-700 text-sm flex items-center justify-between gap-3 animate-fadeIn">
            <div className="flex items-center gap-2.5 min-w-0">
              <AlertCircle className="h-5 w-5 text-red-600 shrink-0" />
              <p className="font-medium truncate">{errorMessage}</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {lastQuery && (
                <button
                  onClick={handleRetry}
                  disabled={isLoading}
                  className="px-3 py-1 rounded-btn bg-red-600 text-white text-xs font-semibold hover:bg-red-700 transition-colors flex items-center gap-1 shadow-sm"
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
                  <span>Try again</span>
                </button>
              )}
              <button
                onClick={() => setErrorMessage(null)}
                className="text-red-500 hover:text-red-800 text-xs font-bold px-2 py-1"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* ── Home Hero Screen (When no messages exist) ──────────────────────── */}
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-8 md:py-12 max-w-2xl mx-auto w-full gap-8">
            {/* Hero Heading */}
            <div className="space-y-2">
              <h1 className="text-2xl md:text-3xl font-semibold text-octo-charcoal tracking-tight">
                How can I help?
              </h1>
              <p className="text-base text-octo-muted max-w-lg mx-auto">
                Ask a question about your manual or describe a problem you're trying to solve.
              </p>
            </div>

            {/* Hero Microphone Voice Button */}
            <div className="w-full flex justify-center">
              <AudioRecorder onRecordingComplete={handleAudioComplete} disabled={isLoading} variant="hero" />
            </div>

            {/* Main Question Search Bar */}
            <div className="w-full space-y-3">
              <ChatInput onSend={handleSend} onAudioComplete={handleAudioComplete} disabled={isLoading} />

              {/* Quick Topic Prompts */}
              <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                <span className="text-xs text-octo-muted mr-1 font-medium">Ask about:</span>
                {[
                  "Error code fix",
                  "Installation instructions",
                  "Water leak troubleshooting",
                  "Filter cleaning",
                ].map((topic) => (
                  <button
                    key={topic}
                    onClick={() => handleSend(`How do I handle ${topic.toLowerCase()}?`)}
                    className="px-3 py-1.5 rounded-full text-xs font-medium bg-white border border-octo-border text-octo-charcoal hover:border-octo-orange hover:bg-octo-orange-light transition-all shadow-sm"
                  >
                    {topic}
                  </button>
                ))}
              </div>
            </div>

            {/* Quick Action Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 w-full pt-4">
              <button
                onClick={startGuidedTroubleshooting}
                className="octo-card p-5 text-left flex items-start gap-4 hover:border-octo-orange transition-all duration-200 group"
              >
                <div className="p-3 rounded-btn bg-octo-orange-light text-octo-orange group-hover:bg-octo-orange group-hover:text-white transition-colors">
                  <Wrench className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-octo-charcoal">Fix a problem</h3>
                  <p className="text-xs text-octo-muted mt-1 leading-relaxed">
                    Guided step-by-step repair assistance for machine issues.
                  </p>
                </div>
              </button>

              <Link
                href="/admin"
                className="octo-card p-5 text-left flex items-start gap-4 hover:border-octo-orange transition-all duration-200 group"
              >
                <div className="p-3 rounded-btn bg-octo-surface-warm text-octo-charcoal group-hover:bg-octo-orange group-hover:text-white transition-colors">
                  <FileText className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-octo-charcoal">My manuals</h3>
                  <p className="text-xs text-octo-muted mt-1 leading-relaxed">
                    Upload new manuals or view indexed document guides.
                  </p>
                </div>
              </Link>
            </div>
          </div>
        ) : (
          /* ── Chat & Answer Screen (When messages exist) ──────────────────── */
          <div className="flex-1 flex flex-col justify-between min-h-0">
            {/* Header bar actions for active chat */}
            <div className="flex justify-between items-center pb-2 border-b border-octo-border text-xs text-octo-muted mb-2">
              <span className="font-semibold text-octo-charcoal">
                {isTroubleshooting ? "🔧 Guided Troubleshooting Mode" : "Assistant Conversation"}
              </span>
              <button
                onClick={clearChat}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg hover:bg-octo-surface-warm text-octo-muted hover:text-red-700 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Clear chat</span>
              </button>
            </div>

            {/* Chat Stream Window */}
            <ChatWindow
              messages={messages}
              isLoading={isLoading}
              isMuted={isMuted}
              onSuggestionClick={handleSend}
              lastUserQuery={lastQuery || ""}
            />

            {/* Guided Troubleshooting Quick Choice Buttons */}
            {isTroubleshooting && !isLoading && (
              <div className="max-w-[780px] mx-auto w-full mb-3 p-4 octo-card-subtle flex flex-col gap-3 animate-fadeIn">
                <span className="text-xs font-semibold text-octo-charcoal">Quick repair response:</span>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={() => handleSend("Yes, the power light is ON.")}
                    className="flex-1 min-w-[120px] h-12 rounded-btn bg-white border border-octo-border hover:border-emerald-600 text-octo-charcoal font-semibold text-sm flex items-center justify-center gap-2 shadow-sm active:scale-95"
                  >
                    <span>👍 YES</span>
                  </button>
                  <button
                    onClick={() => handleSend("No, the power light is OFF.")}
                    className="flex-1 min-w-[120px] h-12 rounded-btn bg-white border border-octo-border hover:border-red-600 text-octo-charcoal font-semibold text-sm flex items-center justify-center gap-2 shadow-sm active:scale-95"
                  >
                    <span>👎 NO</span>
                  </button>
                </div>
              </div>
            )}

            {/* Fixed Bottom Input Bar */}
            <div className="pt-3 border-t border-octo-border bg-octo-bg sticky bottom-0">
              <div className="max-w-[850px] mx-auto w-full">
                <ChatInput onSend={handleSend} onAudioComplete={handleAudioComplete} disabled={isLoading} />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
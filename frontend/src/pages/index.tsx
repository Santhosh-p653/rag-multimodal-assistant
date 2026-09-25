import { useState, useEffect, useCallback, useRef } from "react";
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
  History,
  Plus
} from "lucide-react";
import { ChatWindow } from "../components/ChatWindow";
import { ChatInput } from "../components/ChatInput";
import { AudioRecorder } from "../components/AudioRecorder";
import { Message } from "../components/MessageBubble";
import { ToastContainer, ToastMessage } from "../components/Toast";
import { ChatHistorySidebar } from "../components/ChatHistorySidebar";
import {
  sendMessage,
  fetchFiles,
  transcribeAudio,
  StoredSession,
  saveSessionBackend,
  deleteSessionBackend,
} from "../lib/api";

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

  // Persistent User & Chat History State
  const [userId, setUserId] = useState<string>("user_default");
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const addToast = useCallback((type: ToastMessage["type"], title: string, description?: string) => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, type, title, description }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Initialize or restore consistent User ID and Chat Sessions across reloads
  useEffect(() => {
    let uid = localStorage.getItem("octo_user_id");
    if (!uid) {
      uid = `user_${Math.random().toString(36).substring(2, 9)}_${Date.now().toString(36)}`;
      localStorage.setItem("octo_user_id", uid);
    }
    setUserId(uid);

    // One-time clean slate reset of legacy chat sessions so the website starts completely fresh
    const cleanKey = "octo_clean_fresh_slate_v4";
    if (!localStorage.getItem(cleanKey)) {
      localStorage.removeItem(`octo_chat_sessions_${uid}`);
      localStorage.removeItem(`octo_active_session_id_${uid}`);
      localStorage.setItem(cleanKey, "true");
      setSessions([]);
      setMessages([]);
      return;
    }

    const savedRaw = localStorage.getItem(`octo_chat_sessions_${uid}`);
    let parsedSessions: StoredSession[] = [];
    if (savedRaw) {
      try {
        parsedSessions = JSON.parse(savedRaw);
        setSessions(parsedSessions);
      } catch (e) {
        console.error("Failed to parse saved chat history:", e);
      }
    }

    const savedActiveId = localStorage.getItem(`octo_active_session_id_${uid}`);
    if (savedActiveId && parsedSessions.length > 0) {
      const active = parsedSessions.find((s) => s.id === savedActiveId);
      if (active && active.messages && active.messages.length > 0) {
        setActiveSessionId(active.id);
        setMessages(
          active.messages.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp),
          }))
        );
        if (active.selectedFile !== undefined) setSelectedFile(active.selectedFile);
        if (active.isTroubleshooting !== undefined) setIsTroubleshooting(active.isTroubleshooting);
      }
    }
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

  // Synchronize conversation turn to localStorage and backend
  const syncSession = useCallback(
    (
      newMessages: Message[],
      currentSessId: string | null,
      troubleshooting: boolean,
      fileFilter: string | null
    ) => {
      if (newMessages.length === 0) return currentSessId;

      const uid = localStorage.getItem("octo_user_id") || userId;
      const now = Date.now();
      let sessId = currentSessId;
      if (!sessId) {
        sessId = `sess_${Math.random().toString(36).substring(2, 9)}_${now.toString(36)}`;
        setActiveSessionId(sessId);
        localStorage.setItem(`octo_active_session_id_${uid}`, sessId);
      }

      const firstUserMsg = newMessages.find((m) => m.sender === "user");
      const defaultTitle = firstUserMsg ? firstUserMsg.text.slice(0, 45) : "Technical inquiry";

      setSessions((prev) => {
        const idx = prev.findIndex((s) => s.id === sessId);
        let updated: StoredSession[];
        if (idx >= 0) {
          const old = prev[idx];
          const newTitle = !old.title || old.title === "New Conversation" ? defaultTitle : old.title;
          updated = [...prev];
          updated[idx] = {
            ...old,
            title: newTitle,
            messages: newMessages,
            updatedAt: now,
            selectedFile: fileFilter,
            isTroubleshooting: troubleshooting,
          };
        } else {
          updated = [
            {
              id: sessId!,
              title: defaultTitle,
              createdAt: now,
              updatedAt: now,
              messages: newMessages,
              selectedFile: fileFilter,
              isTroubleshooting: troubleshooting,
            },
            ...prev,
          ];
        }
        localStorage.setItem(`octo_chat_sessions_${uid}`, JSON.stringify(updated));
        return updated;
      });

      // Background sync to backend
      saveSessionBackend({
        session_id: sessId,
        user_id: uid,
        title: defaultTitle,
        messages: newMessages,
        status: troubleshooting ? "TROUBLESHOOTING" : "ACTIVE",
      });

      return sessId;
    },
    [userId]
  );

  const handleSend = async (text: string, imageBase64?: string) => {
    if ((!text || !text.trim()) && !imageBase64) return;
    setErrorMessage(null);
    setLastQuery(text || "Image Query");

    let sessId = activeSessionId;
    if (!sessId) {
      sessId = `sess_${Math.random().toString(36).substring(2, 9)}_${Date.now().toString(36)}`;
      setActiveSessionId(sessId);
      if (userId) {
        localStorage.setItem(`octo_active_session_id_${userId}`, sessId);
      }
    }

    const userMsg: Message = {
      id: Math.random().toString(36).substring(7),
      sender: "user",
      text: text || "Uploaded image for diagnostic search",
      query_image: imageBase64,
      timestamp: new Date(),
    };

    const nextWithUser = [...messages, userMsg];
    setMessages(nextWithUser);
    syncSession(nextWithUser, sessId, isTroubleshooting, selectedFile);
    setIsLoading(true);

    try {
      const data = await sendMessage(text, selectedFile, sessId, hintLang, imageBase64);
      const assistantMsg: Message = {
        id: Math.random().toString(36).substring(7),
        sender: "assistant",
        text: data.answer,
        sources: data.sources,
        images: data.images,
        timestamp: new Date(),
      };
      const finalMessages = [...nextWithUser, assistantMsg];
      setMessages(finalMessages);
      syncSession(finalMessages, sessId, isTroubleshooting, selectedFile);
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

  // Chat History thread management handlers
  const handleNewChat = () => {
    const newId = `sess_${Math.random().toString(36).substring(2, 9)}_${Date.now().toString(36)}`;
    setActiveSessionId(newId);
    if (userId) {
      localStorage.setItem(`octo_active_session_id_${userId}`, newId);
    }
    setMessages([]);
    setErrorMessage(null);
    setLastQuery(null);
    setIsTroubleshooting(false);
    addToast("info", "New chat started");
  };

  const handleSelectSession = (sessionId: string) => {
    const target = sessions.find((s) => s.id === sessionId);
    if (!target) return;
    setActiveSessionId(sessionId);
    if (userId) {
      localStorage.setItem(`octo_active_session_id_${userId}`, sessionId);
    }
    setMessages(
      target.messages.map((m: any) => ({
        ...m,
        timestamp: new Date(m.timestamp),
      }))
    );
    setSelectedFile(target.selectedFile || null);
    setIsTroubleshooting(!!target.isTroubleshooting);
    setErrorMessage(null);
    setLastQuery(null);
    addToast("info", "Loaded conversation", target.title);
  };

  const handleDeleteSession = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updated = sessions.filter((s) => s.id !== sessionId);
    setSessions(updated);
    if (userId) {
      localStorage.setItem(`octo_chat_sessions_${userId}`, JSON.stringify(updated));
      deleteSessionBackend(sessionId);
    }
    if (activeSessionId === sessionId) {
      handleNewChat();
    }
    addToast("info", "Deleted conversation");
  };

  const handleClearAllSessions = () => {
    if (confirm("Are you sure you want to clear all conversation history?")) {
      setSessions([]);
      if (userId) {
        localStorage.removeItem(`octo_chat_sessions_${userId}`);
        localStorage.removeItem(`octo_active_session_id_${userId}`);
      }
      handleNewChat();
      addToast("info", "All conversation history cleared");
    }
  };

  const clearChat = () => {
    handleNewChat();
  };

  const startGuidedTroubleshooting = () => {
    setIsTroubleshooting(true);
    handleSend("Help me troubleshoot and fix a problem with my machine step by step.");
  };

  return (
    <div className={`flex flex-col min-h-screen bg-octo-bg text-octo-charcoal size-${textSize}`}>
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* Chat History Slide-out Drawer */}
      <ChatHistorySidebar
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onClearAll={handleClearAllSessions}
        userId={userId}
      />

      {/* ── Top Header ─────────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-octo-border sticky top-0 z-30 shadow-sm">
        <div className="max-w-[1100px] mx-auto px-4 h-16 flex items-center justify-between">
          {/* Logo & Identity (Anchored to Top-Left Corner) */}
          <div className="flex items-center gap-2 sm:gap-3">
            <Link href="/" onClick={handleNewChat} className="flex items-center gap-2 group">
              <span className="text-xl font-bold tracking-tight text-octo-charcoal">
                OCTO <span className="text-octo-orange">RAG</span>
              </span>
            </Link>

            {/* System Status Indicator */}
            <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-octo-surface-warm border border-octo-border text-octo-charcoal font-medium">
              <span className={`h-2 w-2 rounded-full ${backendOnline ? "bg-emerald-600" : "bg-amber-500 animate-pulse"}`} />
              <span>{backendOnline ? "System ready" : "Connecting..."}</span>
            </div>

            {/* History Toggle Button */}
            <button
              onClick={() => setIsHistoryOpen(true)}
              className="px-2.5 py-1.5 rounded-lg border border-octo-border bg-octo-surface-warm/50 text-octo-charcoal hover:bg-octo-surface-warm transition-colors flex items-center gap-1.5 shadow-sm text-xs font-semibold"
              title="Open Chat History"
            >
              <History className="h-4 w-4 text-octo-orange" />
              <span className="hidden sm:inline">History</span>
              {sessions.length > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-white text-octo-orange border border-octo-border">
                  {sessions.length}
                </span>
              )}
            </button>

            {/* New Chat Quick Button */}
            <button
              onClick={handleNewChat}
              className="p-1.5 sm:px-2.5 sm:py-1.5 rounded-lg border border-octo-border bg-white text-octo-charcoal hover:bg-octo-surface-warm transition-colors flex items-center gap-1 shadow-sm text-xs font-semibold"
              title="Start a new chat"
            >
              <Plus className="h-3.5 w-3.5 text-octo-orange" />
              <span className="hidden sm:inline">New</span>
            </button>
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

              <button
                onClick={() => handleSend("What are the common diagnostic error codes and troubleshooting steps for my equipment?")}
                className="octo-card p-5 text-left flex items-start gap-4 hover:border-octo-orange transition-all duration-200 group"
              >
                <div className="p-3 rounded-btn bg-octo-surface-warm text-octo-charcoal group-hover:bg-octo-orange group-hover:text-white transition-colors">
                  <FileText className="h-6 w-6" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-octo-charcoal">Diagnostic Codes</h3>
                  <p className="text-xs text-octo-muted mt-1 leading-relaxed">
                    Lookup error codes, multimeter specs, and sensor tests.
                  </p>
                </div>
              </button>
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
              hintLang={hintLang}
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
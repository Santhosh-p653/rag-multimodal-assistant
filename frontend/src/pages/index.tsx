import { useState, useEffect } from "react";
import Link from "next/link";
import { MessageSquare, FileText, Wifi, WifiOff, Trash2, Sparkles, AlertCircle, Database, Volume2, VolumeX } from "lucide-react";
import { ChatWindow } from "../components/ChatWindow";
import { ChatInput } from "../components/ChatInput";
import { Message } from "../components/MessageBubble";
import { sendMessage, fetchFiles, transcribeAudio } from "../lib/api";

interface HealthInfo {
  status: string;
  llm_provider: string;
  vectors_stored: number;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(true);
  const [hintLang, setHintLang] = useState("auto");

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
    setErrorMessage(null);
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
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      setErrorMessage(err.message || "Could not reach the assistant.");
      setMessages((prev) => [
        ...prev,
        {
          id: Math.random().toString(36).substring(7),
          sender: "assistant",
          text: "⚠️ Connection Error: Could not reach the backend.",
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
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
        setErrorMessage("Speech not recognized. Please try again or speak more clearly.");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to transcribe audio.");
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setErrorMessage(null);
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 glass-panel border-r border-slate-800 flex flex-col justify-between shrink-0 hidden md:flex">
        <div className="p-6">
          {/* Logo */}
          <div className="flex items-center space-x-2.5 mb-8">
            <div className="p-2 bg-violet-600 rounded-xl shadow-lg shadow-violet-500/30">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-wide bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                M-RAG Assistant
              </h1>
              <p className="text-[10px] text-violet-400 font-medium">Phase 3 — RAG</p>
            </div>
          </div>

          {/* Nav */}
          <nav className="space-y-1.5">
            <Link href="/" className="flex items-center space-x-3 px-4 py-3 rounded-xl bg-violet-600/10 text-violet-400 border border-violet-500/20 font-medium text-sm transition-all">
              <MessageSquare className="h-4 w-4" />
              <span>Chat Assistant</span>
            </Link>
            <Link href="/admin" className="flex items-center space-x-3 px-4 py-3 rounded-xl text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent hover:border-slate-800/50 font-medium text-sm transition-all">
              <FileText className="h-4 w-4" />
              <span>Document Upload</span>
            </Link>
          </nav>
        </div>

        {/* Status Footer */}
        <div className="p-6 border-t border-slate-900 space-y-2">
          {/* Backend online/offline */}
          <div className="flex items-center justify-between bg-slate-900/50 border border-slate-800/80 rounded-xl px-4 py-2.5 text-xs">
            <span className="text-slate-400">Backend API</span>
            <div className="flex items-center space-x-1.5">
              {backendOnline === null ? (
                <div className="h-2 w-2 rounded-full bg-slate-600 animate-pulse" />
              ) : backendOnline ? (
                <>
                  <span className="text-emerald-400 font-medium">Online</span>
                  <Wifi className="h-3.5 w-3.5 text-emerald-400" />
                </>
              ) : (
                <>
                  <span className="text-rose-400 font-medium">Offline</span>
                  <WifiOff className="h-3.5 w-3.5 text-rose-400" />
                </>
              )}
            </div>
          </div>

          {/* LLM Provider */}
          {health && (
            <div className="flex items-center justify-between bg-slate-900/50 border border-slate-800/80 rounded-xl px-4 py-2.5 text-xs">
              <span className="text-slate-400">LLM</span>
              <span className={`font-medium capitalize ${health.llm_provider === "none" ? "text-rose-400" : "text-emerald-400"}`}>
                {health.llm_provider === "none" ? "No key set" : health.llm_provider}
              </span>
            </div>
          )}

          {/* Vectors stored */}
          {health && (
            <div className="flex items-center justify-between bg-slate-900/50 border border-slate-800/80 rounded-xl px-4 py-2.5 text-xs">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Database className="h-3 w-3" /> Vectors
              </span>
              <span className="font-medium text-violet-400">{health.vectors_stored.toLocaleString()}</span>
            </div>
          )}
        </div>
      </aside>

      {/* Main Chat */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        <header className="h-16 border-b border-slate-900 flex items-center justify-between px-6 md:px-8 bg-slate-950/80 backdrop-blur-md shrink-0">
          <div className="flex items-center space-x-3 md:space-x-0">
            <div className="md:hidden flex items-center space-x-2">
              <Link href="/admin" className="p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-900 rounded-lg">
                <FileText className="h-5 w-5" />
              </Link>
            </div>
            <h2 className="text-sm font-semibold text-slate-100">Chat Session</h2>
          </div>

          <div className="flex items-center space-x-4">
            <div className="md:hidden">
              {backendOnline ? <Wifi className="h-4 w-4 text-emerald-400" /> : <WifiOff className="h-4 w-4 text-rose-400" />}
            </div>
            {backendOnline && (
              <button
                onClick={() => setIsMuted(!isMuted)}
                className={`p-2 rounded-lg border transition-all duration-200 ${
                  isMuted
                    ? "border-slate-800 bg-slate-900/20 text-slate-500 hover:text-slate-350 hover:bg-slate-900/40"
                    : "border-violet-500/30 bg-violet-600/10 text-violet-400 hover:bg-violet-600/20"
                }`}
                title={isMuted ? "Unmute voice responses" : "Mute voice responses"}
              >
                {isMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
              </button>
            )}
            {backendOnline && (
              <div className="flex items-center space-x-2">
                <span className="text-xs text-slate-500 hidden sm:inline">Source:</span>
                <select
                  value={selectedFile || ""}
                  onChange={(e) => setSelectedFile(e.target.value || null)}
                  className="bg-slate-900 border border-slate-800 text-xs text-slate-350 px-2 py-1 rounded-md focus:outline-none focus:border-violet-500/50 transition-all max-w-[120px] sm:max-w-[180px] truncate"
                >
                  <option value="">All Manuals</option>
                  {files.map((file) => (
                    <option key={file} value={file}>
                      {file}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {messages.length > 0 && (
              <button onClick={clearChat} className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-900/40 text-xs text-slate-400 hover:text-rose-400 hover:bg-rose-500/5 transition-all">
                <Trash2 className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Clear Chat</span>
              </button>
            )}
          </div>
        </header>

        {errorMessage && (
          <div className="mx-6 mt-4 p-3.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs flex items-start space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{errorMessage}</span>
          </div>
        )}

        <ChatWindow messages={messages} isLoading={isLoading} isMuted={isMuted} />

        <footer className="p-6 md:p-8 border-t border-slate-900 bg-slate-950/80 backdrop-blur-md shrink-0">
          <div className="max-w-4xl mx-auto space-y-3">
            {backendOnline && (
              <div className="flex justify-between items-center px-1">
                <div className="flex items-center space-x-2 text-[11px]">
                  <span className="text-slate-500 font-medium">Transcribe Language:</span>
                  <select
                    value={hintLang}
                    onChange={(e) => setHintLang(e.target.value)}
                    className="bg-slate-900 border border-slate-800 text-slate-350 px-2 py-1 rounded-md focus:outline-none focus:border-violet-500/50 transition-all cursor-pointer"
                  >
                    <option value="auto">🗣️ Auto-detect (Indic / English)</option>
                    <option value="en">🇬🇧 English</option>
                    <option value="hi">🇮🇳 Hindi</option>
                    <option value="ta">🇮🇳 Tamil</option>
                    <option value="te">🇮🇳 Telugu</option>
                    <option value="kn">🇮🇳 Kannada</option>
                    <option value="ml">🇮🇳 Malayalam</option>
                    <option value="bn">🇮🇳 Bengali</option>
                    <option value="mr">🇮🇳 Marathi</option>
                  </select>
                </div>
                <div className="text-[10px] text-slate-500 font-medium">
                  {isMuted ? "🔇 Voice response off" : "🔊 Voice response on"}
                </div>
              </div>
            )}
            <ChatInput onSend={handleSend} onAudioComplete={handleAudioComplete} disabled={isLoading} />
            <p className="text-[10px] text-center text-slate-500 mt-2.5">
              Answers are grounded in your uploaded documents. Upload manuals via the admin panel.
            </p>
          </div>
        </footer>
      </main>
    </div>
  );
}
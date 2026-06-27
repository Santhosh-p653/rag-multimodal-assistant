import React, { useEffect, useRef } from "react";
import { MessageBubble, Message } from "./MessageBubble";
import { HelpCircle, Sparkles } from "lucide-react";

interface ChatWindowProps {
  messages: Message[];
  isLoading?: boolean;
  isMuted?: boolean;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({ messages, isLoading, isMuted = true }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Automatically scroll to bottom when messages or loading state changes
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full text-center max-w-md mx-auto space-y-4 my-12">
          <div className="p-4 bg-violet-600/10 rounded-3xl border border-violet-500/20 text-violet-400">
            <Sparkles className="h-8 w-8 animate-pulse" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">Welcome to Multimodal RAG Assistant</h3>
            <p className="text-sm text-slate-400 mt-1">
              Ask anything to get started, or head to the admin panel to upload documents to build your knowledge base.
            </p>
          </div>
          
          <div className="grid grid-cols-1 gap-2 w-full pt-4">
            <div className="flex items-center text-xs text-slate-500 bg-slate-900/50 border border-slate-800 rounded-xl px-4 py-3">
              <HelpCircle className="h-4 w-4 mr-2.5 text-violet-400 shrink-0" />
              <span>Backend endpoint automatically checks connection.</span>
            </div>
          </div>
        </div>
      ) : (
        messages.map((msg) => <MessageBubble key={msg.id} message={msg} isMuted={isMuted} />)
      )}

      {/* Loading State Bubble */}
      {isLoading && (
        <div className="flex w-full justify-start mb-4">
          <div className="flex items-start max-w-[80%] md:max-w-[70%]">
            <div className="flex items-center justify-center h-9 w-9 rounded-full bg-slate-800 border border-slate-700/50 mr-3 shrink-0">
              <Sparkles className="h-4 w-4 text-violet-400 animate-spin" />
            </div>
            <div>
              <div className="px-4 py-3 rounded-2xl bg-slate-900 border border-slate-800 text-slate-400 rounded-tl-none flex items-center space-x-1 min-h-[44px]">
                <span className="h-2 w-2 bg-slate-400 rounded-full loading-dot"></span>
                <span className="h-2 w-2 bg-slate-400 rounded-full loading-dot"></span>
                <span className="h-2 w-2 bg-slate-400 rounded-full loading-dot"></span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

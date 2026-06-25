import React from "react";
import { MessageSquare, Cpu, FileText } from "lucide-react";

export interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  sources?: string[];       // Phase 3: source documents cited in the answer
  timestamp: Date;
}

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.sender === "user";

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`flex items-start max-w-[80%] md:max-w-[70%] ${isUser ? "flex-row-reverse" : "flex-row"}`}>

        {/* Avatar */}
        <div
          className={`flex items-center justify-center h-9 w-9 rounded-full shrink-0 ${
            isUser
              ? "ml-3 bg-gradient-to-tr from-violet-600 to-indigo-600 shadow-lg shadow-violet-500/20"
              : "mr-3 bg-slate-800 border border-slate-700/50"
          }`}
        >
          {isUser ? (
            <MessageSquare className="h-4 w-4 text-white" />
          ) : (
            <Cpu className="h-4 w-4 text-violet-400" />
          )}
        </div>

        {/* Bubble + Sources */}
        <div className="flex flex-col gap-2">
          <div
            className={`px-4 py-3 rounded-2xl shadow-sm leading-relaxed text-sm ${
              isUser
                ? "bg-gradient-to-tr from-violet-600 to-indigo-600 text-white rounded-tr-none border border-violet-500/30"
                : "bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none"
            }`}
          >
            <p className="whitespace-pre-wrap">{message.text}</p>
          </div>

          {/* Source citations — only for assistant messages with sources */}
          {!isUser && message.sources && message.sources.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-1">
              <span className="text-[10px] text-slate-500 self-center mr-1">Sources:</span>
              {message.sources.map((src) => (
                <span
                  key={src}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20"
                >
                  <FileText className="h-2.5 w-2.5" />
                  {src}
                </span>
              ))}
            </div>
          )}

          {/* Timestamp */}
          <p
            className={`text-[10px] text-slate-500 px-1 ${isUser ? "text-right" : "text-left"}`}
          >
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </div>
    </div>
  );
};

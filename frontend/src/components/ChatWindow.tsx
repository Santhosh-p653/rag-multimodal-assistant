import React, { useEffect, useRef } from "react";
import { MessageBubble, Message } from "./MessageBubble";
import { Bot } from "lucide-react";

interface ChatWindowProps {
  messages: Message[];
  isLoading?: boolean;
  isMuted?: boolean;
  onSuggestionClick?: (text: string) => void;
  lastUserQuery?: string;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  messages,
  isLoading,
  isMuted = true,
  onSuggestionClick,
  lastUserQuery = "",
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 max-w-[850px] mx-auto w-full">
      {messages.map((msg, index) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          isMuted={isMuted}
          onSuggestionClick={onSuggestionClick}
          userQuery={msg.sender === "user" ? msg.text : lastUserQuery}
        />
      ))}

      {/* Loading State Indicator */}
      {isLoading && (
        <div className="flex w-full justify-start my-4">
          <div className="flex items-start gap-3.5 max-w-[780px]">
            <div className="flex items-center justify-center h-10 w-10 rounded-full bg-octo-surface-warm border border-octo-border shrink-0">
              <Bot className="h-5 w-5 text-octo-orange animate-pulse" />
            </div>
            <div className="octo-card p-4 rounded-tl-none flex items-center gap-2">
              <span className="text-sm font-medium text-octo-muted">Searching your manuals...</span>
              <div className="flex gap-1.5 ml-2">
                <span className="h-2 w-2 bg-octo-orange rounded-full animate-bounce"></span>
                <span className="h-2 w-2 bg-octo-orange rounded-full animate-bounce [animation-delay:0.2s]"></span>
                <span className="h-2 w-2 bg-octo-orange rounded-full animate-bounce [animation-delay:0.4s]"></span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};

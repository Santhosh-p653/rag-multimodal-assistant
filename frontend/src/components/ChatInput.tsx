import React, { useState, KeyboardEvent } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, disabled }) => {
  const [value, setValue] = useState("");

  const handleSend = () => {
    if (!value.trim() || disabled) return;
    onSend(value);
    setValue("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  return (
    <div className="relative flex items-center w-full">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? "Waiting for assistant..." : "Ask the assistant..."}
        disabled={disabled}
        className="w-full glass-input px-5 py-4 pr-14 rounded-2xl text-slate-100 text-sm focus:outline-none transition-all placeholder-slate-500 disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        className={`absolute right-2.5 p-2 rounded-xl transition-all duration-200 ${
          disabled || !value.trim()
            ? "text-slate-600 bg-transparent cursor-not-allowed"
            : "text-white bg-violet-600 hover:bg-violet-500 shadow-md shadow-violet-500/20 active:scale-95"
        }`}
        aria-label="Send message"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  );
};

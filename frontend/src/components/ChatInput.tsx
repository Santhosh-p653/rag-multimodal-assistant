import React, { useState, KeyboardEvent } from "react";
import { Send } from "lucide-react";
import { AudioRecorder } from "./AudioRecorder";

interface ChatInputProps {
  onSend: (message: string) => void;
  onAudioComplete: (blob: Blob) => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, onAudioComplete, disabled }) => {
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
    <div className="flex items-center gap-3 w-full">
      <AudioRecorder onRecordingComplete={onAudioComplete} disabled={disabled} variant="compact" />

      <div className="relative flex items-center w-full">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? "Processing..." : "Ask about your manual..."}
          disabled={disabled}
          className="w-full octo-input px-5 h-12 pr-14 text-octo-charcoal text-base placeholder:text-octo-muted disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className={`absolute right-1.5 h-9 w-9 rounded-btn flex items-center justify-center transition-all duration-200 ${
            disabled || !value.trim()
              ? "text-octo-muted bg-transparent cursor-not-allowed opacity-40"
              : "text-white bg-octo-orange hover:bg-octo-orange-hover shadow-sm active:scale-95"
          }`}
          aria-label="Send question"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

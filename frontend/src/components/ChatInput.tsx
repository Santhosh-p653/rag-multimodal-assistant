import React, { useState, useRef, KeyboardEvent, ClipboardEvent } from "react";
import { Send, Paperclip, X, Image as ImageIcon } from "lucide-react";
import { AudioRecorder } from "./AudioRecorder";

interface ChatInputProps {
  onSend: (message: string, imageBase64?: string) => void;
  onAudioComplete: (blob: Blob) => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSend, onAudioComplete, disabled }) => {
  const [value, setValue] = useState("");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imageFileName, setImageFileName] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if ((!value.trim() && !imageBase64) || disabled) return;
    onSend(value.trim() || "What does this image/schematic show?", imageBase64 || undefined);
    setValue("");
    setImageBase64(null);
    setImageFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImageFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const b64 = event.target?.result as string;
      setImageBase64(b64);
    };
    reader.readAsDataURL(file);
  };

  const handlePaste = (e: ClipboardEvent<HTMLDivElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        const file = items[i].getAsFile();
        if (file) {
          setImageFileName("Pasted Screenshot");
          const reader = new FileReader();
          reader.onload = (event) => {
            const b64 = event.target?.result as string;
            setImageBase64(b64);
          };
          reader.readAsDataURL(file);
          e.preventDefault();
          break;
        }
      }
    }
  };

  const clearAttachment = () => {
    setImageBase64(null);
    setImageFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col gap-2 w-full" onPaste={handlePaste}>
      {/* Attached Image Preview Chip */}
      {imageBase64 && (
        <div className="flex items-center gap-2 px-3 py-1.5 bg-octo-surface-warm border border-octo-border rounded-lg self-start shadow-xs animate-in fade-in slide-in-from-bottom-2 duration-150">
          <div className="relative w-8 h-8 rounded overflow-hidden shrink-0 border border-octo-border/60">
            <img src={imageBase64} alt="Attached query preview" className="w-full h-full object-cover" />
          </div>
          <span className="text-xs font-medium text-octo-charcoal truncate max-w-[180px]">
            {imageFileName || "Attached Image"}
          </span>
          <button
            type="button"
            onClick={clearAttachment}
            className="p-1 text-octo-muted hover:text-red-500 rounded transition-colors"
            title="Remove attachment"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Main Input Row */}
      <div className="flex items-center gap-2 sm:gap-3 w-full">
        {/* Voice Trigger */}
        <AudioRecorder onRecordingComplete={onAudioComplete} disabled={disabled} variant="compact" />

        {/* Input Bar with Attachment and Send */}
        <div className="relative flex items-center w-full">
          {/* Paperclip / File Picker Button */}
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
            className="absolute left-3 p-1.5 text-octo-muted hover:text-octo-charcoal rounded-md transition-colors"
            title="Attach schematic, part photo, or wiring diagram"
          >
            <Paperclip className="h-4 w-4" />
          </button>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="image/*"
            className="hidden"
          />

          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? "Processing..."
                : imageBase64
                ? "Ask a question about this attached image..."
                : "Ask about your manual or paste a diagram..."
            }
            disabled={disabled}
            className="w-full octo-input pl-10 pr-14 h-12 text-octo-charcoal text-base placeholder:text-octo-muted disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          />

          <button
            onClick={handleSend}
            disabled={disabled || (!value.trim() && !imageBase64)}
            className={`absolute right-1.5 h-9 w-9 rounded-btn flex items-center justify-center transition-all duration-200 ${
              disabled || (!value.trim() && !imageBase64)
                ? "text-octo-muted bg-transparent cursor-not-allowed opacity-40"
                : "text-white bg-octo-orange hover:bg-octo-orange-hover shadow-sm active:scale-95"
            }`}
            aria-label="Send question"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

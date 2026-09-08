import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Bot, FileText, Volume2, Loader2, VolumeX } from "lucide-react";
import { speakText } from "../lib/api";
import { VisualDisplay } from "./VisualDisplay";

export interface RetrievedImage {
  image_id: string;
  document_id: string;
  page: number;
  caption: string;
  url: string;
}

export interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  sources?: string[];       // Source documents cited in the answer
  images?: RetrievedImage[]; // Associated visual diagrams
  timestamp: Date;
}

interface MessageBubbleProps {
  message: Message;
  isMuted?: boolean;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, isMuted = true }) => {
  const isUser = message.sender === "user";
  const [isTtsLoading, setIsTtsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const playAudio = async () => {
    if (isPlaying) {
      if (audioRef.current) {
        audioRef.current.pause();
        setIsPlaying(false);
      }
      return;
    }

    setIsTtsLoading(true);
    try {
      const audioUrl = await speakText(message.text, "auto");

      if (audioRef.current) {
        audioRef.current.pause();
      }

      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onplay = () => {
        setIsPlaying(true);
        setIsTtsLoading(false);
      };

      audio.onended = () => {
        setIsPlaying(false);
      };

      audio.onerror = () => {
        setIsPlaying(false);
        setIsTtsLoading(false);
      };

      await audio.play();
    } catch (err) {
      console.error("TTS Playback failed:", err);
      setIsPlaying(false);
      setIsTtsLoading(false);
    }
  };

  useEffect(() => {
    if (message.sender === "assistant" && !isMuted) {
      playAudio();
    }

    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} my-4`}>
      <div className={`flex items-start max-w-[92%] sm:max-w-[85%] md:max-w-[780px] ${isUser ? "flex-row-reverse gap-3" : "flex-row gap-3.5"}`}>

        {/* Avatar */}
        <div
          className={`flex items-center justify-center h-10 w-10 rounded-full shrink-0 shadow-sm ${
            isUser
              ? "bg-octo-orange text-white"
              : "bg-octo-surface-warm border border-octo-border text-octo-charcoal"
          }`}
        >
          {isUser ? (
            <MessageSquare className="h-5 w-5" />
          ) : (
            <Bot className="h-5 w-5 text-octo-orange" />
          )}
        </div>

        {/* Message Content Container */}
        <div className="flex flex-col gap-2.5 min-w-0 flex-1">
          {/* Main Bubble Card */}
          <div
            className={`p-5 rounded-card shadow-sm ${
              isUser
                ? "bg-octo-surface-warm border border-octo-border text-octo-charcoal rounded-tr-none text-base md:text-[17px] font-medium leading-relaxed"
                : "octo-card text-octo-charcoal text-base md:text-[18px] leading-[1.65]"
            }`}
          >
            <p className="whitespace-pre-wrap">{message.text}</p>
          </div>

          {/* Inline Diagrams & Visual Schematics */}
          {!isUser && message.images && message.images.length > 0 && (
            <VisualDisplay images={message.images} />
          )}

          {/* Controls & Citations Bar */}
          {!isUser && (
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              {/* Citations list */}
              <div className="flex flex-wrap items-center gap-2 text-xs text-octo-muted">
                {message.sources && message.sources.length > 0 && (
                  <>
                    <span className="font-semibold text-octo-charcoal">Based on:</span>
                    {message.sources.map((src) => (
                      <span
                        key={src}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-octo-surface-warm text-octo-charcoal border border-octo-border"
                      >
                        <FileText className="h-3.5 w-3.5 text-octo-orange" />
                        {src}
                      </span>
                    ))}
                  </>
                )}
              </div>

              {/* Speaker Play/Pause Button */}
              <button
                onClick={playAudio}
                disabled={isTtsLoading}
                className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-btn border text-xs font-semibold transition-all duration-200 ${
                  isPlaying
                    ? "bg-octo-orange text-white border-octo-orange shadow-sm"
                    : "bg-white text-octo-charcoal border-octo-border hover:bg-octo-surface-warm"
                }`}
                title={isPlaying ? "Pause audio response" : "Listen to answer"}
              >
                {isTtsLoading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-octo-orange" />
                    <span>Loading audio...</span>
                  </>
                ) : isPlaying ? (
                  <>
                    <VolumeX className="h-3.5 w-3.5" />
                    <span>Pause audio</span>
                  </>
                ) : (
                  <>
                    <Volume2 className="h-3.5 w-3.5 text-octo-orange" />
                    <span>🔊 Listen to answer</span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* Timestamp */}
          <p className={`text-xs text-octo-muted ${isUser ? "text-right" : "text-left"}`}>
            {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
      </div>
    </div>
  );
};

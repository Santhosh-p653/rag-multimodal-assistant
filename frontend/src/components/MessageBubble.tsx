import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Cpu, FileText, Volume2, Loader2 } from "lucide-react";
import { speakText } from "../lib/api";

export interface Message {
  id: string;
  sender: "user" | "assistant";
  text: string;
  sources?: string[];       // Phase 3: source documents cited in the answer
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
    // Autoplay if assistant bubble is mounted and muted setting is off
    if (message.sender === "assistant" && !isMuted) {
      playAudio();
    }

    return () => {
      // Stop playback on component unmount
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

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

        {/* Bubble + Sources + Speaker */}
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

          {/* Controls Footer - only for assistant */}
          {!isUser && (
            <div className="flex items-center justify-between w-full mt-0.5 px-1 gap-4">
              {/* Sources badges */}
              <div className="flex flex-wrap gap-1.5">
                {message.sources && message.sources.length > 0 && (
                  <>
                    <span className="text-[10px] text-slate-500 self-center mr-1">Sources:</span>
                    {message.sources.map((src) => (
                      <span
                        key={src}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-violet-500/10 text-violet-400 border border-violet-500/20 animate-fadeIn"
                      >
                        <FileText className="h-2.5 w-2.5" />
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
                className={`p-1.5 rounded-xl border transition-all duration-200 hover:scale-105 active:scale-95 shrink-0 ${
                  isPlaying
                    ? "border-violet-500/30 bg-violet-600/20 text-violet-400 shadow-md shadow-violet-500/10"
                    : "border-slate-800 bg-slate-900/35 text-slate-500 hover:text-slate-350 hover:bg-slate-900"
                }`}
                title={isPlaying ? "Pause audio response" : "Play audio response"}
              >
                {isTtsLoading ? (
                  <Loader2 className="h-3 w-3 animate-spin text-violet-400" />
                ) : (
                  <Volume2 className="h-3 w-3" />
                )}
              </button>
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


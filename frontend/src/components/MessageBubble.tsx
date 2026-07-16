import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Cpu, FileText, Volume2, Loader2 } from "lucide-react";
import { speakText } from "../lib/api";

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
  sources?: string[];       // Phase 3: source documents cited in the answer
  images?: RetrievedImage[]; // Phase 3: associated images
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

          {/* Phase 3: Visuals Rendering */}
          {!isUser && message.images && message.images.length > 0 && (
            <div className="flex flex-col gap-3 mt-2 mb-2 w-full max-w-sm">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider pl-1">Related Visuals</span>
              {message.images.map((img) => (
                <div key={img.image_id} className="flex flex-col bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden p-2 group transition-all duration-300 hover:border-violet-500/50 hover:bg-slate-900 shadow-sm">
                  <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-slate-950 flex items-center justify-center">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={`http://localhost:8000${img.url}`}
                      alt={img.caption}
                      className="object-contain max-h-full max-w-full group-hover:scale-[1.02] transition-transform duration-500"
                    />
                  </div>
                  <div className="mt-2.5 px-1.5 flex flex-col gap-1 pb-1">
                    <p className="text-xs text-slate-200 font-medium leading-snug line-clamp-2" title={img.caption}>
                      {img.caption}
                    </p>
                    <p className="text-[10px] text-slate-500 flex justify-between items-center">
                      <span className="truncate max-w-[70%] text-slate-400">{img.document_id}</span>
                      <span className="shrink-0 bg-slate-800 px-1.5 py-0.5 rounded text-violet-400 border border-slate-700 font-medium">Page {img.page}</span>
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}

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


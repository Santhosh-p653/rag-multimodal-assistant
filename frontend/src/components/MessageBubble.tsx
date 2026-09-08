import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Bot, FileText, Volume2, Loader2, VolumeX, ChevronDown, ChevronUp, AlertCircle, Sparkles } from "lucide-react";
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
  onSuggestionClick?: (suggestionText: string) => void;
  userQuery?: string;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  isMuted = true,
  onSuggestionClick,
  userQuery = "",
}) => {
  const isUser = message.sender === "user";
  const [isTtsLoading, setIsTtsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const isNoEvidence =
    !isUser &&
    (message.text.includes("could not find that information") ||
      message.text.includes("couldn't find"));

  const isLongAnswer = !isUser && message.text.length > 320;
  const isDiagramRequested =
    Boolean(userQuery && /diagram|schematic|drawing|picture|visual/i.test(userQuery));

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
    if (message.sender === "assistant" && !isMuted && !isNoEvidence) {
      playAudio();
    }

    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  // Generate contextual follow-up suggestions
  const getFollowUpSuggestions = () => {
    if (isUser || isNoEvidence) return [];

    const textLower = message.text.toLowerCase();
    const suggestions = [];

    if (textLower.includes("error") || textLower.includes("fault") || textLower.includes("code")) {
      suggestions.push("What caused this error code?");
      suggestions.push("Show step-by-step fix");
    } else if (textLower.includes("install") || textLower.includes("mount") || textLower.includes("setup")) {
      suggestions.push("What tools do I need?");
      suggestions.push("Common installation mistakes");
    } else if (textLower.includes("clean") || textLower.includes("filter") || textLower.includes("maintenance")) {
      suggestions.push("How often should I clean this?");
      suggestions.push("Show component location diagram");
    } else {
      suggestions.push("How do I fix this?");
      suggestions.push("Show related diagram");
    }

    return suggestions.slice(0, 3);
  };

  const suggestions = getFollowUpSuggestions();

  return (
    <div className={`flex w-full ${isUser ? "justify-end" : "justify-start"} my-4`}>
      <div className={`flex items-start max-w-[92%] sm:max-w-[85%] md:max-w-[780px] ${isUser ? "flex-row-reverse gap-3" : "flex-row gap-3.5"}`}>

        {/* Avatar */}
        <div
          className={`flex items-center justify-center h-10 w-10 rounded-full shrink-0 shadow-sm ${
            isUser
              ? "bg-octo-orange text-white"
              : isNoEvidence
              ? "bg-amber-100 border border-amber-300 text-amber-800"
              : "bg-octo-surface-warm border border-octo-border text-octo-charcoal"
          }`}
        >
          {isUser ? (
            <MessageSquare className="h-5 w-5" />
          ) : isNoEvidence ? (
            <AlertCircle className="h-5 w-5 text-amber-700" />
          ) : (
            <Bot className="h-5 w-5 text-octo-orange" />
          )}
        </div>

        {/* Message Content Container */}
        <div className="flex flex-col gap-2.5 min-w-0 flex-1">
          {/* Main Card */}
          {isNoEvidence ? (
            /* Honest No-Evidence Card */
            <div className="octo-card p-5 border-amber-200 bg-amber-50/40 text-octo-charcoal space-y-3">
              <div className="flex items-center gap-2 text-amber-800 font-semibold text-sm">
                <AlertCircle className="h-4 w-4 text-amber-600" />
                <span>Information Not Found in Manuals</span>
              </div>
              <p className="text-base text-octo-charcoal leading-relaxed">
                I couldn't find relevant details in your uploaded manuals for this question. I don't want to guess or fabricate an answer.
              </p>
              <div className="pt-2 flex flex-wrap gap-2">
                {onSuggestionClick && (
                  <>
                    <button
                      onClick={() => onSuggestionClick("What error codes are described in the manual?")}
                      className="px-3 py-1.5 rounded-full text-xs font-medium bg-white border border-amber-200 text-octo-charcoal hover:border-octo-orange transition-all shadow-sm"
                    >
                      💡 Try asking about error codes
                    </button>
                    <button
                      onClick={() => onSuggestionClick("Show available manuals")}
                      className="px-3 py-1.5 rounded-full text-xs font-medium bg-white border border-amber-200 text-octo-charcoal hover:border-octo-orange transition-all shadow-sm"
                    >
                      📄 Check uploaded manuals
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            /* Normal Information Card */
            <div
              className={`p-5 rounded-card shadow-sm ${
                isUser
                  ? "bg-octo-surface-warm border border-octo-border text-octo-charcoal rounded-tr-none text-base md:text-[17px] font-medium leading-relaxed"
                  : "octo-card text-octo-charcoal text-base md:text-[18px] leading-[1.65]"
              }`}
            >
              <p className="whitespace-pre-wrap">
                {isLongAnswer && !isExpanded
                  ? message.text.slice(0, 300) + "..."
                  : message.text}
              </p>

              {/* Progressive Disclosure Toggle */}
              {isLongAnswer && (
                <button
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="mt-3 text-xs font-semibold text-octo-orange hover:underline flex items-center gap-1 focus:outline-none"
                >
                  {isExpanded ? (
                    <>
                      <span>Show less</span>
                      <ChevronUp className="h-3.5 w-3.5" />
                    </>
                  ) : (
                    <>
                      <span>Show full details</span>
                      <ChevronDown className="h-3.5 w-3.5" />
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Visual Diagrams with Honest Fallback */}
          {!isUser && (
            <VisualDisplay
              images={message.images}
              isDiagramRequested={isDiagramRequested}
            />
          )}

          {/* Context-Aware Follow-Up Suggestions */}
          {!isUser && !isNoEvidence && suggestions.length > 0 && onSuggestionClick && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="text-xs font-semibold text-octo-muted">Next steps:</span>
              {suggestions.map((sug) => (
                <button
                  key={sug}
                  onClick={() => onSuggestionClick(sug)}
                  className="px-3 py-1 rounded-full text-xs font-medium bg-white border border-octo-border text-octo-charcoal hover:border-octo-orange hover:bg-octo-orange-light transition-all shadow-sm"
                >
                  {sug}
                </button>
              ))}
            </div>
          )}

          {/* Controls & Citations Bar */}
          {!isUser && !isNoEvidence && (
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

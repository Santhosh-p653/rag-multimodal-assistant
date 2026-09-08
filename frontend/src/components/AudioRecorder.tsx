import React, { useState, useRef, useEffect } from "react";
import { Mic, Square, AlertCircle } from "lucide-react";

interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  disabled?: boolean;
  variant?: "hero" | "compact";
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onRecordingComplete,
  disabled = false,
  variant = "compact",
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [permissionError, setPermissionError] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  const startRecording = async () => {
    setPermissionError(false);
    audioChunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mediaRecorder.mimeType });
        onRecordingComplete(audioBlob);

        // Stop all audio tracks in stream to release microphone
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone permission denied:", err);
      setPermissionError(true);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  if (variant === "hero") {
    return (
      <div className="flex flex-col items-center gap-2 w-full max-w-sm">
        {permissionError && (
          <span className="text-xs text-red-700 bg-red-50 border border-red-200 px-3 py-1.5 rounded-lg flex items-center gap-1.5 animate-fadeIn">
            <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />
            Microphone access was blocked by your browser.
          </span>
        )}

        <button
          onClick={isRecording ? stopRecording : startRecording}
          disabled={disabled}
          type="button"
          className={`w-full h-14 px-6 rounded-btn text-base font-semibold transition-all duration-200 flex items-center justify-center gap-3 shadow-sm ${
            isRecording
              ? "bg-red-600 hover:bg-red-700 text-white"
              : "bg-octo-orange hover:bg-octo-orange-hover text-white active:scale-[0.98]"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          title={isRecording ? "Stop recording speech query" : "Tap to speak your question"}
        >
          {isRecording ? (
            <>
              <Square className="h-5 w-5 fill-white" />
              <span>🎤 Listening... Tap to stop</span>

              {/* Waveform visualizer bars */}
              <div className="flex items-center gap-1 ml-2">
                <span className="h-3 w-1 bg-white rounded-full animate-bounce"></span>
                <span className="h-5 w-1 bg-white rounded-full animate-bounce [animation-delay:0.15s]"></span>
                <span className="h-2 w-1 bg-white rounded-full animate-bounce [animation-delay:0.3s]"></span>
                <span className="h-4 w-1 bg-white rounded-full animate-bounce [animation-delay:0.45s]"></span>
              </div>
            </>
          ) : (
            <>
              <Mic className="h-5 w-5" />
              <span>Tap to speak</span>
            </>
          )}
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {permissionError && (
        <span className="text-xs text-red-700 bg-red-50 border border-red-200 px-2.5 py-1 rounded-lg flex items-center gap-1 animate-fadeIn">
          <AlertCircle className="h-3.5 w-3.5 text-red-600" /> Mic blocked
        </span>
      )}

      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled}
        className={`h-12 px-4 rounded-btn font-medium text-sm transition-all duration-200 flex items-center gap-2 border ${
          isRecording
            ? "bg-red-600 text-white border-red-700"
            : "bg-octo-surface-warm text-octo-charcoal border-octo-border hover:bg-[#E4DCD0] disabled:opacity-50 disabled:cursor-not-allowed"
        }`}
        type="button"
        title={isRecording ? "Stop recording" : "Speak query"}
      >
        {isRecording ? (
          <>
            <Square className="h-4 w-4 fill-white" />
            <span className="font-semibold text-xs">Listening...</span>
            <div className="flex items-center gap-0.5 ml-1">
              <span className="h-2 w-0.5 bg-white animate-pulse"></span>
              <span className="h-3 w-0.5 bg-white animate-pulse [animation-delay:0.2s]"></span>
              <span className="h-1.5 w-0.5 bg-white animate-pulse [animation-delay:0.4s]"></span>
            </div>
          </>
        ) : (
          <>
            <Mic className="h-4.5 w-4.5 text-octo-orange" />
            <span className="hidden sm:inline text-xs font-medium">Speak</span>
          </>
        )}
      </button>
    </div>
  );
};

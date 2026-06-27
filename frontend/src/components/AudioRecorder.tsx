import React, { useState, useRef, useEffect } from "react";
import { Mic, Square, AlertCircle } from "lucide-react";

interface AudioRecorderProps {
  onRecordingComplete: (blob: Blob) => void;
  disabled?: boolean;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onRecordingComplete,
  disabled = false,
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
    // Cleanup on unmount
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return (
    <div className="flex items-center space-x-2">
      {permissionError && (
        <span className="text-[10px] text-rose-400 flex items-center gap-1 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1.5 rounded-xl animate-fadeIn">
          <AlertCircle className="h-3.5 w-3.5" /> Mic blocked
        </span>
      )}

      <button
        onClick={isRecording ? stopRecording : startRecording}
        disabled={disabled}
        className={`p-3 rounded-2xl transition-all duration-300 relative ${
          isRecording
            ? "text-white bg-rose-600 hover:bg-rose-500 shadow-md shadow-rose-500/30 scale-105"
            : "text-slate-400 bg-slate-900 border border-slate-800 hover:bg-slate-800 hover:text-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
        }`}
        type="button"
        title={isRecording ? "Stop recording" : "Record audio query"}
      >
        {isRecording ? (
          <>
            <Square className="h-4.5 w-4.5 animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
            </span>
          </>
        ) : (
          <Mic className="h-4.5 w-4.5" />
        )}
      </button>
    </div>
  );
};

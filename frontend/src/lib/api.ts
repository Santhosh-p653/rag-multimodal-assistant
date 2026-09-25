const API_URL = "http://localhost:8000";

// Updated: answer + sources shape for Phase 3 RAG
export interface ChatResponse {
  answer: string;
  sources: string[];
  images?: Array<{
    image_id: string;
    document_id: string;
    page: number;
    caption: string;
    url: string;
  }>;
}

export interface UploadResponse {
  filename: string;
  markdown_file: string;
  chunks_ingested: number;
  status: string;
}

/**
 * Sends a chat message to the RAG backend.
 * Returns a grounded answer and list of source documents.
 */
export async function sendMessage(
  message: string,
  sourceFile: string | null = null,
  sessionId?: string | null,
  language?: string | null
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/agent/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: message,
      source_input: sourceFile,
      session_id: sessionId || undefined,
      language: language && language !== "auto" ? language : undefined,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Backend error" }));
    throw new Error(errorData.detail || "Failed to get response from assistant");
  }

  const data = await response.json();
  
  // Format sources if they are objects (AgentResponse format)
  let formattedSources: string[] = [];
  if (data.sources && Array.isArray(data.sources)) {
    formattedSources = data.sources.map((s: any) => {
      if (typeof s === "string") return s;
      if (s.page) return `${s.source} (Page ${s.page})`;
      return s.source;
    });
  }
  
  let finalAnswer = data.answer || data.clarification_question || "";
  if (data.steps && Array.isArray(data.steps) && data.steps.length > 0) {
    finalAnswer += "\n\n**Diagnostic Steps:**\n" + data.steps.map((step: string) => `- ${step}`).join("\n");
  }
  
  return {
    answer: finalAnswer,
    sources: formattedSources,
    images: data.images || [],
  };
}

/**
 * Fetches the list of unique uploaded files from the backend.
 */
export async function fetchFiles(): Promise<string[]> {
  const response = await fetch(`${API_URL}/files`);
  if (!response.ok) {
    throw new Error("Failed to fetch documents");
  }
  const data = await response.json();
  return data.files || [];
}

/**
 * Deletes a manual and its search index from the backend.
 */
export async function deleteFile(filename: string): Promise<{ status: string; filename: string }> {
  const response = await fetch(`${API_URL}/files/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to delete ${filename}`);
  }
  return response.json();
}

/**
 * Uploads a document with real-time progress tracking via XMLHttpRequest.
 */
export function uploadDocument(
  file: File,
  onProgress: (percent: number) => void
): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.open("POST", `${API_URL}/upload`, true);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResponse);
        } catch {
          reject(new Error("Failed to parse upload response"));
        }
      } else {
        try {
          const err = JSON.parse(xhr.responseText);
          reject(new Error(err.detail || "Upload failed"));
        } catch {
          reject(new Error(`Server error: ${xhr.status}`));
        }
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.send(formData);
  });
}

/**
 * Sends recorded audio to the STT /transcribe endpoint.
 * Returns transcription text and detected language.
 */
export async function transcribeAudio(
  audioBlob: Blob,
  hintLang: string
): Promise<{ text: string; detected_language: string }> {
  const formData = new FormData();
  const ext = audioBlob.type?.includes("webm")
    ? "webm"
    : audioBlob.type?.includes("ogg")
    ? "ogg"
    : "wav";
  formData.append("audio", audioBlob, `query.${ext}`);
  formData.append("hint_lang", hintLang);

  const response = await fetch(`${API_URL}/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Transcription failed" }));
    throw new Error(errorData.detail || "Failed to transcribe audio query");
  }

  return response.json();
}

/**
 * Sends text to the TTS /speak endpoint and returns the audio object URL.
 */
export async function speakText(text: string, language: string): Promise<string> {
  const response = await fetch(`${API_URL}/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language }),
  });

  if (!response.ok) {
    throw new Error("Failed to generate speech");
  }

  const audioBlob = await response.blob();
  return URL.createObjectURL(audioBlob);
}

// ─── Chat Session Persistence Helpers ─────────────────────────────────────

export interface SessionSummary {
  session_id: string;
  user_id: string;
  title: string;
  created_at: number;
  updated_at: number;
  message_count: number;
  last_message: string;
  product?: string;
  status?: string;
}

export interface StoredSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: any[];
  selectedFile?: string | null;
  isTroubleshooting?: boolean;
}

export async function fetchUserSessions(userId: string): Promise<SessionSummary[]> {
  try {
    const res = await fetch(`${API_URL}/sessions?user_id=${encodeURIComponent(userId)}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.sessions || [];
  } catch (err) {
    console.warn("Backend session fetch failed (offline or network error):", err);
    return [];
  }
}

export async function saveSessionBackend(payload: {
  session_id: string;
  user_id: string;
  title?: string;
  messages?: any[];
  product?: string;
  status?: string;
}): Promise<void> {
  try {
    await fetch(`${API_URL}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    console.warn("Backend session save failed (offline or network error):", err);
  }
}

export async function deleteSessionBackend(sessionId: string): Promise<void> {
  try {
    await fetch(`${API_URL}/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    });
  } catch (err) {
    console.warn("Backend session delete failed:", err);
  }
}

// ─── PostgreSQL Audit & Manual Registry Helpers ───────────────────────────

export interface AuditTurn {
  id: number;
  session_id: string;
  sender: string;
  message_text: string;
  question?: string | null;
  action?: string | null;
  created_at?: string;
}

export interface AuditSummary {
  total_sessions: number;
  total_turns: number;
  total_manuals: number;
  recent_activity: AuditTurn[];
}

export interface ManualRecord {
  id: number;
  filename: string;
  equipment_type: string;
  model?: string | null;
  file_hash: string;
  chunks_count: number;
  created_at?: string;
}

export async function fetchAuditSummary(): Promise<AuditSummary> {
  const response = await fetch(`${API_URL}/admin/audit`);
  if (!response.ok) {
    throw new Error("Failed to retrieve audit summary from backend");
  }
  return response.json();
}

export async function fetchManualRegistry(): Promise<{ files: string[]; registry: ManualRecord[] }> {
  const response = await fetch(`${API_URL}/files`);
  if (!response.ok) {
    throw new Error("Failed to retrieve manual registry");
  }
  return response.json();
}



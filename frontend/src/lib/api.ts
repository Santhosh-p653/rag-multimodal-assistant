const API_URL = "http://localhost:8000";

// Updated: answer + sources shape for Phase 3 RAG
export interface ChatResponse {
  answer: string;
  sources: string[];
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
  sourceFile: string | null = null
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, source_file: sourceFile }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Backend error" }));
    throw new Error(errorData.detail || "Failed to get response from assistant");
  }

  return response.json();
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
  formData.append("audio", audioBlob, "query.wav");
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

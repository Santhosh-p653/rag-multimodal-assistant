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
export async function sendMessage(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: "Backend error" }));
    throw new Error(errorData.detail || "Failed to get response from assistant");
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

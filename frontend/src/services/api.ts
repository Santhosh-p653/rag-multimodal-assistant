const API_URL = "http://localhost:8000";

export async function sendMessage(message: string, sourceFile: string | null = null) {
  const response = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      source_file: sourceFile,
    }),
  });

  return response.json();
}
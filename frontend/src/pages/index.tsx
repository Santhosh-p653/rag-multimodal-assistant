import { useState } from "react";
import { sendMessage } from "../services/api";

export default function Home() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<string[]>([]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage = `You: ${input}`;

    const data = await sendMessage(input);

    const botMessage = `Assistant: ${data.response}`;

    setMessages((prev) => [...prev, userMessage, botMessage]);

    setInput("");
  };

  return (
    <div style={{ padding: "20px" }}>
      <h1>RAG Multimodal Assistant</h1>

      <div
        style={{
          border: "1px solid #ccc",
          minHeight: "300px",
          padding: "10px",
          marginBottom: "20px",
        }}
      >
        {messages.map((msg, index) => (
          <p key={index}>{msg}</p>
        ))}
      </div>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type message..."
        style={{
          width: "70%",
          padding: "10px",
        }}
      />

      <button
        onClick={handleSend}
        style={{
          marginLeft: "10px",
          padding: "10px",
        }}
      >
        Send
      </button>
    </div>
  );
}
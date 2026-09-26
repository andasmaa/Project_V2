import React, { useState, useRef, useEffect } from "react";
import AgentFlowGraph from "./AgentFlowGraph";

const COLORS = {
  primary: "#F26522",
  primaryLight: "#FF8C42",
  dark: "#1A1A1A",
  light: "#FFFFFF",
  grayLight: "#F8F9FA",
  gray: "#6C757D",
  grayDark: "#343A40",
  success: "#22c55e",
};

const S = {
  page: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #F26522 0%, #FF8C42 100%)",
    display: "flex",
    alignItems: "stretch",
    justifyContent: "center",
    gap: 24,
    padding: 16,
    fontFamily: "'Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', sans-serif",
    flexWrap: "nowrap",
  },
  shell: {
    display: "flex",
    flexDirection: "column",
    background: COLORS.light,
    borderRadius: 28,
    boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
    overflow: "hidden",
    width: 400,
    flexShrink: 0,
    height: "calc(100vh - 32px)",
    maxWidth: "100%",
  },
  graphPanel: {
    flex: 1,  
    minWidth: 500,     
    height: "calc(100vh - 32px)",
    borderRadius: 28,
    boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
    overflow: "hidden",
  },
  header: {
    background: COLORS.light,
    padding: "20px 20px 12px 20px",
    borderBottom: `1px solid ${COLORS.grayLight}`,
    flexShrink: 0,
  },
  headerTitle: { color: COLORS.dark, fontWeight: 700, fontSize: 18, margin: 0, letterSpacing: "-0.5px" },
  headerSubtitle: { color: COLORS.gray, fontSize: 12, margin: "4px 0 0 0" },
  avatarWrap: {
    width: 44, height: 44, borderRadius: 16, background: COLORS.primary,
    display: "flex", alignItems: "center", justifyContent: "center", marginRight: 8,
  },
  botAvatarSmall: {
    width: 32, height: 32, borderRadius: 12, background: COLORS.primary,
    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
  },
  messages: { flex: 1, overflowY: "auto", padding: "16px 16px 8px 16px", background: COLORS.grayLight },
  inputBar: { padding: "12px 16px", borderTop: `1px solid ${COLORS.grayLight}`, flexShrink: 0, background: COLORS.light },
  inputRow: {
    display: "flex", alignItems: "center", gap: 10,
    background: COLORS.grayLight, borderRadius: 30, padding: "4px 4px 4px 18px",
  },
  input: { flex: 1, border: "none", background: "transparent", outline: "none", fontSize: 15, color: COLORS.dark, padding: "10px 0" },
  footer: { textAlign: "center", fontSize: 10, color: COLORS.gray, marginTop: 6, letterSpacing: "0.3px" },
};

function BotAvatar({ size = "small" }) {
  const wrap = size === "large" ? S.avatarWrap : S.botAvatarSmall;
  const sz = size === "large" ? 22 : 18;
  return (
    <div style={wrap}>
      <svg width={sz} height={sz} viewBox="0 0 24 24" fill="none">
        <rect x="4" y="8" width="16" height="10" rx="3" fill="white" opacity="0.95" />
        <rect x="8" y="4" width="8" height="5" rx="2" fill="white" opacity="0.8" />
        <circle cx="9" cy="13" r="1.5" fill={COLORS.primary} />
        <circle cx="15" cy="13" r="1.5" fill={COLORS.primary} />
      </svg>
    </div>
  );
}

function Message({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, marginBottom: 16, flexDirection: isUser ? "row-reverse" : "row" }}>
      {!isUser && <BotAvatar />}
      <div style={{
        maxWidth: "72%", padding: "12px 16px",
        borderRadius: isUser ? "20px 20px 4px 20px" : "20px 20px 20px 4px",
        background: isUser ? COLORS.primary : COLORS.light,
        color: isUser ? COLORS.light : COLORS.dark,
        fontSize: 14, lineHeight: 1.45, wordBreak: "break-word",
        boxShadow: isUser ? "none" : "0 2px 8px rgba(0,0,0,0.04)",
        border: isUser ? "none" : `1px solid ${COLORS.grayLight}`,
      }}>
        {msg.content}
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, marginBottom: 16 }}>
      <BotAvatar />
      <div style={{ background: COLORS.light, borderRadius: "20px 20px 20px 4px", padding: "12px 18px", display: "flex", gap: 6, border: `1px solid ${COLORS.grayLight}` }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ width: 7, height: 7, borderRadius: "50%", background: COLORS.primary, opacity: 0.6, animation: `awbBounce 1.2s ${i * 0.2}s infinite` }} />
        ))}
      </div>
    </div>
  );
}

export default function ChatInterface() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Bonjour, je suis votre assistant bancaire. Comment puis-je vous aider ?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const graphRef = useRef(null); // 🔥 référence vers AgentFlowGraph

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    const session_id = localStorage.getItem("session_id");

    // 🔥 Déclenche la visualisation du flux en parallèle de l'appel /chat
    graphRef.current?.sendMessage(text);

    try {
      const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: messages, session_id }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response || data.message || "Veuillez réessayer." },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Service momentanément indisponible." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const canSend = !!input.trim() && !loading;
  const sessionId = localStorage.getItem("session_id") || "anonymous";

  return (
    <div style={S.page}>
      <style>{`
        @keyframes awbBounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-5px)} }
        input::placeholder{color:#B0B0B0}
        ::-webkit-scrollbar{width:4px}
        ::-webkit-scrollbar-track{background:#F0F0F0}
        ::-webkit-scrollbar-thumb{background:#C0C0C0;border-radius:4px}
      `}</style>

      {/* Chat existant */}
      <div style={S.shell}>
        <div style={S.header}>
          <div style={{ display: "flex", alignItems: "center" }}>
            <BotAvatar size="large" />
            <div>
              <p style={S.headerTitle}>AWB Connect</p>
              <p style={S.headerSubtitle}>Assistant bancaire</p>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: COLORS.success }} />
            <span style={{ color: COLORS.gray, fontSize: 10 }}>En ligne</span>
          </div>
        </div>

        <div style={S.messages}>
          {messages.map((m, i) => <Message key={i} msg={m} />)}
          {loading && <TypingDots />}
          <div ref={bottomRef} />
        </div>

        <div style={S.inputBar}>
          <div style={S.inputRow}>
            <input
              style={S.input}
              placeholder="Écrivez votre message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              disabled={loading}
            />
            <button
              onClick={send}
              style={{
                width: 38, height: 38, borderRadius: "50%", border: "none",
                background: canSend ? COLORS.primary : COLORS.grayLight,
                cursor: canSend ? "pointer" : "default",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.2s",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={canSend ? COLORS.light : COLORS.gray} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
          <p style={S.footer}>AWB AI · Service client disponible 24/7</p>
        </div>
      </div>

      {/* 🔥 Visualisation du flux, à côté du chat */}
      <div style={S.graphPanel}>
        <AgentFlowGraph ref={graphRef} sessionId={sessionId} />
      </div>
    </div>
  );
}
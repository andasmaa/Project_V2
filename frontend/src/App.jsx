// frontend/src/App.jsx
import React, { useState } from "react";
import ChatInterface from "./components/ChatInterface";
import MetricsDashboard from "./components/MetricsDashboard";
import AuditLog from "./components/AuditLog";
import RAGPage from "./components/RAGPage";
import MonitoringPage from "./components/MonitoringPage";
import SupervisorDashboard from "./components/SupervisorDashboard";
import HomePage from "./components/HomePage";
import LoginPage from "./components/LoginPage";


// ─── Composant principal de l'app bancaire (6 onglets) ──────────────────────
const BankingApp = () => {
  const [tab, setTab] = useState("chat");

  const TABS = [
    { id: "chat",       label: "Chat" },
    { id: "metrics",    label: "Métriques" },
    { id: "audit",      label: "Audit" },
    { id: "rag",        label: "RAG" },
    { id: "hitl",       label: "HITL" },
    { id: "monitoring", label: "Monitoring" },
  ];

  return (
    <div style={appStyles.app}>
      {/* ============ NAVBAR ============ */}
      <nav style={appStyles.nav}>
        <div style={appStyles.navLeft}>
          <div style={appStyles.logo}>
            <span style={appStyles.logoText}>A</span>
          </div>
          <span style={appStyles.brand}>AWB Connect</span>
        </div>

        <div style={appStyles.tabsContainer}>
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              style={{
                ...appStyles.tabButton,
                background: tab === t.id ? "#F26522" : "transparent",
                color: tab === t.id ? "#FFFFFF" : "#6C757D",
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={appStyles.statusContainer}>
          <div style={appStyles.statusDot} />
          <span style={appStyles.statusText}>Backend connecté</span>
        </div>
      </nav>

      {/* ============ CONTENU ============ */}
      <div style={appStyles.content} key={tab}>
        {tab === "chat"       && <ChatInterface />}
        {tab === "metrics"    && <MetricsDashboard />}
        {tab === "audit"      && <AuditLog />}
        {tab === "rag"        && <RAGPage />}
        {tab === "hitl"       && <SupervisorDashboard />}
        {tab === "monitoring" && <MonitoringPage />}
      </div>
    </div>
  );
};

// ─── App racine ─────────────────────────────────────────────────────────────
export default function App() {
  const [stage, setStage] = useState("home"); // "home" → "login" → "app"

  if (stage === "home") {
    return <HomePage onGetStarted={() => setStage("login")} />;
  }

  if (stage === "login") {
    return <LoginPage onLoginSuccess={() => setStage("app")} />;
  }

  return <BankingApp />;
}

// ─── Styles ─────────────────────────────────────────────────────────────────
const appStyles = {
  app: {
    display: "flex",
    flexDirection: "column",
    minHeight: "100vh",
    background: "linear-gradient(135deg, #F26522 0%, #FF8C42 100%)",
    fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
  },
  nav: {
    background: "#FFFFFF",
    padding: "12px 24px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexWrap: "wrap",
    gap: "16px",
    position: "sticky",
    top: 0,
    zIndex: 100,
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
    pointerEvents: "auto",
  },
  navLeft: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexShrink: 0,
  },
  logo: {
    width: "36px",
    height: "36px",
    borderRadius: "12px",
    background: "#F26522",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 4px 8px rgba(242,101,34,0.3)",
  },
  logoText: {
    color: "#FFFFFF",
    fontWeight: 700,
    fontSize: "18px",
  },
  brand: {
    fontWeight: 700,
    color: "#1A1A1A",
    fontSize: "16px",
    letterSpacing: "-0.3px",
  },
  tabsContainer: {
    display: "flex",
    gap: "4px",
    background: "#F8F9FA",
    padding: "4px",
    borderRadius: "40px",
    overflowX: "auto",
    flex: 1,
    maxWidth: "100%",
    justifyContent: "center",
  },
  tabButton: {
    padding: "8px 18px",
    borderRadius: "32px",
    fontSize: "13px",
    fontWeight: 600,
    border: "none",
    cursor: "pointer",
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    transition: "all 0.2s ease",
    fontFamily: "inherit",
    whiteSpace: "nowrap",
    position: "relative",
    zIndex: 1,
  },
  statusContainer: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    background: "#F8F9FA",
    padding: "6px 14px",
    borderRadius: "30px",
    flexShrink: 0,
  },
  statusDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#22c55e",
    animation: "pulse 1.5s infinite",
  },
  statusText: {
    fontSize: "12px",
    color: "#6C757D",
    fontWeight: 500,
  },
  content: {
    flex: 1,
    minHeight: 0,
    position: "relative",
    zIndex: 1,
  },
};

// Animation CSS globale
const styleSheet = document.createElement("style");
styleSheet.textContent = `
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.8); }
  }
  button:hover { transform: scale(1.02); transition: transform 0.2s; }
  ::-webkit-scrollbar { height: 6px; width: 6px; }
  ::-webkit-scrollbar-thumb { background: #F26522; border-radius: 3px; }
`;
document.head.appendChild(styleSheet);
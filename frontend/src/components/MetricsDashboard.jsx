// frontend/src/components/MetricsDashboard.jsx
import React, { useState, useEffect } from "react";

const COLORS = {
  primary: "#F26522",      // Orange AWB
  primaryLight: "#FF8C42",
  dark: "#1A1A1A",
  light: "#FFFFFF",
  gray: "#6C757D",
  grayLight: "#F8F9FA",
  success: "#22c55e",
};

export default function MetricsDashboard() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/metrics")
      .then(r => r.json())
      .then(d => {
        console.log("Métriques reçues:", d);
        setMetrics(d);
      })
      .catch(err => {
        console.error("Erreur métriques:", err);
        setMetrics(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const cards = [
    { label: "Requêtes traitées", value: metrics?.total_requests ?? 0, color: COLORS.primary },
    { label: "Taux de succès", value: metrics?.success_rate ? `${metrics.success_rate}%` : "0%", color: COLORS.success },
    { label: "Temps moyen (ms)", value: metrics?.avg_response_time_ms ?? 0, color: "#f59e0b" },
    { label: "Escalades humaines", value: metrics?.hitl_requests ?? 0, color: "#ef4444" },
  ];

  const extraStats = [
    { label: "Top agent", value: metrics?.top_agent ?? "—", color: COLORS.primary },
    { label: "Uptime", value: metrics?.uptime_hours ? `${metrics.uptime_hours}h` : "0h", color: COLORS.primaryLight },
    { label: "RAG utilisé", value: metrics?.rag_usage_rate ? `${metrics.rag_usage_rate}%` : "0%", color: COLORS.primary },
    { label: "Agents actifs", value: metrics?.active_agents ?? 14, color: COLORS.primaryLight },
  ];

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}></div>
        <p style={styles.loadingText}>Chargement des métriques...</p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div style={styles.errorContainer}>
        <div style={styles.errorCard}>
          <p style={styles.errorText}>Backend inaccessible — métriques indisponibles.</p>
          <p style={styles.errorSubtext}>Vérifiez que le serveur est lancé sur http://localhost:8000</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>Métriques système</h1>
        <p style={styles.subtitle}>Performance et activité de l'assistant bancaire</p>
      </div>

      {/* Cartes principales */}
      <div style={styles.cardsGrid}>
        {cards.map((c, i) => (
          <div key={i} style={styles.card}>
            <div style={{ ...styles.cardBorder, borderTopColor: c.color }}></div>
            <div style={styles.cardContent}>
              <p style={styles.cardLabel}>{c.label}</p>
              <p style={{ ...styles.cardValue, color: c.color }}>{c.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Statistiques avancées */}
      <div style={styles.section}>
        <h2 style={styles.sectionTitle}>Statistiques avancées</h2>
        <div style={styles.statsGrid}>
          {extraStats.map((c, i) => (
            <div key={i} style={styles.statCard}>
              <p style={styles.statLabel}>{c.label}</p>
              <p style={{ ...styles.statValue, color: c.color }}>{c.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Détail par agent */}
      {metrics.requests_by_agent && Object.keys(metrics.requests_by_agent).length > 0 && (
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>Requêtes par agent</h2>
          <div style={styles.agentsContainer}>
            {Object.entries(metrics.requests_by_agent).map(([agent, count]) => (
              <div key={agent} style={styles.agentBadge}>
                <span style={styles.agentName}>{agent}</span>
                <span style={styles.agentCount}>{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: COLORS.light,
    padding: "24px",
  },
  header: {
    marginBottom: "24px",
  },
  title: {
    color: COLORS.dark,
    fontSize: "24px",
    fontWeight: 700,
    margin: 0,
    letterSpacing: "-0.5px",
  },
  subtitle: {
    color: COLORS.gray,
    fontSize: "14px",
    margin: "8px 0 0 0",
  },
  cardsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "16px",
    marginBottom: "24px",
  },
  card: {
    background: COLORS.light,
    borderRadius: "16px",
    overflow: "hidden",
    boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
    border: `1px solid #E5E7EB`,
  },
  cardBorder: {
    height: "4px",
    width: "100%",
  },
  cardContent: {
    padding: "20px",
  },
  cardLabel: {
    fontSize: "12px",
    color: COLORS.gray,
    margin: "0 0 8px 0",
    fontWeight: 500,
  },
  cardValue: {
    fontSize: "28px",
    fontWeight: 700,
    margin: 0,
  },
  section: {
    marginBottom: "24px",
  },
  sectionTitle: {
    fontSize: "16px",
    fontWeight: 600,
    color: COLORS.dark,
    marginBottom: "12px",
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: "12px",
  },
  statCard: {
    background: COLORS.grayLight,
    borderRadius: "16px",
    padding: "16px",
    border: `1px solid #E5E7EB`,
  },
  statLabel: {
    fontSize: "11px",
    color: COLORS.gray,
    margin: "0 0 4px 0",
    fontWeight: 500,
  },
  statValue: {
    fontSize: "20px",
    fontWeight: 700,
    margin: 0,
  },
  agentsContainer: {
    display: "flex",
    flexWrap: "wrap",
    gap: "12px",
  },
  agentBadge: {
    background: COLORS.grayLight,
    borderRadius: "40px",
    padding: "8px 16px",
    display: "flex",
    alignItems: "center",
    gap: "10px",
    border: `1px solid #E5E7EB`,
  },
  agentName: {
    fontSize: "13px",
    fontWeight: 600,
    color: COLORS.dark,
  },
  agentCount: {
    fontSize: "13px",
    fontWeight: 700,
    color: COLORS.primary,
    background: "#FFF0E6",
    padding: "2px 8px",
    borderRadius: "20px",
  },
  loadingContainer: {
    minHeight: "100vh",
    background: COLORS.light,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  loadingSpinner: {
    width: "40px",
    height: "40px",
    border: "3px solid rgba(242,101,34,0.2)",
    borderTopColor: COLORS.primary,
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  loadingText: {
    color: COLORS.primary,
    marginTop: "16px",
    fontSize: "14px",
  },
  errorContainer: {
    minHeight: "100vh",
    background: COLORS.light,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
  },
  errorCard: {
    background: COLORS.light,
    borderRadius: "16px",
    padding: "32px",
    textAlign: "center",
    border: `1px solid #E5E7EB`,
  },
  errorText: {
    color: "#dc2626",
    fontSize: "14px",
    fontWeight: 500,
    margin: 0,
  },
  errorSubtext: {
    color: COLORS.gray,
    fontSize: "12px",
    margin: "8px 0 0 0",
  },
};

// Ajouter l'animation CSS
const styleSheet = document.createElement("style");
styleSheet.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
`;
document.head.appendChild(styleSheet);
// frontend/src/components/SupervisorDashboard.jsx
import React, { useState, useEffect } from "react";

const COLORS = {
  primary: "#F26522",      // Orange AWB
  primaryLight: "#FF8C42", // Orange clair
  dark: "#1A1A1A",         // Noir
  light: "#FFFFFF",        // Blanc
  grayLight: "#F8F9FA",    // Gris très clair
  gray: "#6C757D",         // Gris moyen
  success: "#22c55e",      // Vert (approuver)
  danger: "#ef4444",       // Rouge (rejeter)
  warning: "#f59e0b",      // Orange (en attente)
};

export default function SupervisorDashboard() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/hitl/pending")
      .then(r => r.json())
      .then(data => {
        console.log("📋 HITL Data reçues:", data);
        setRequests(data.requests || []);
        setLoading(false);
      })
      .catch(err => {
        console.error("❌ Erreur HITL:", err);
        setRequests([]);
        setLoading(false);
      });
  }, []);

  const handleApprove = async (requestId) => {
    setActionLoading(requestId);
    try {
      await fetch(`http://localhost:8000/api/hitl/${requestId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approver: "supervisor" })
      });
      setRequests(requests.filter(r => r.request_id !== requestId));
    } catch (err) {
      console.error("Erreur approbation:", err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (requestId) => {
    setActionLoading(requestId);
    try {
      await fetch(`http://localhost:8000/api/hitl/${requestId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Rejeté par superviseur" })
      });
      setRequests(requests.filter(r => r.request_id !== requestId));
    } catch (err) {
      console.error("Erreur rejet:", err);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}></div>
        <p style={styles.loadingText}>Chargement des demandes...</p>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>Supervision</h1>
        <p style={styles.subtitle}>Décisions en attente ({requests.length})</p>
      </div>

      {requests.length === 0 ? (
        <div style={styles.emptyContainer}>
          <svg style={styles.emptyIcon} width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 8v4l3 3M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z" />
            <path d="M12 6v2" />
          </svg>
          <p style={styles.emptyText}>Aucune décision en attente de supervision.</p>
          <p style={styles.emptySubtext}>Les demandes HITL apparaîtront ici.</p>
        </div>
      ) : (
        <div style={styles.requestsContainer}>
          {requests.map((req) => (
            <div key={req.request_id} style={styles.requestCard}>
              <div style={styles.cardHeader}>
                <div style={styles.cardHeaderLeft}>
                  <span style={styles.agentIcon}></span>
                  <span style={styles.agentName}>{req.agent_name || req.agent}</span>
                </div>
                <span style={styles.statusBadge}>
                  <span style={styles.statusDot}></span>
                  En attente
                </span>
              </div>
              <p style={styles.requestContext}>
                {req.context?.substring(0, 180)}...
              </p>
              <div style={styles.cardActions}>
                <button 
                  onClick={() => handleApprove(req.request_id)}
                  disabled={actionLoading === req.request_id}
                  style={actionLoading === req.request_id ? styles.buttonDisabled : styles.buttonApprove}
                >
                  {actionLoading === req.request_id ? "..." : "✓ Approuver"}
                </button>
                <button 
                  onClick={() => handleReject(req.request_id)}
                  disabled={actionLoading === req.request_id}
                  style={actionLoading === req.request_id ? styles.buttonDisabled : styles.buttonReject}
                >
                  {actionLoading === req.request_id ? "..." : "✗ Rejeter"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #F26522 0%, #FF8C42 100%)",
    padding: "24px",
  },
  header: {
    marginBottom: "24px",
  },
  title: {
    color: "#FFFFFF",
    fontSize: "24px",
    fontWeight: 700,
    margin: 0,
    letterSpacing: "-0.5px",
  },
  subtitle: {
    color: "rgba(255,255,255,0.8)",
    fontSize: "14px",
    margin: "8px 0 0 0",
  },
  loadingContainer: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #F26522 0%, #FF8C42 100%)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
  },
  loadingSpinner: {
    width: "40px",
    height: "40px",
    border: "3px solid rgba(255,255,255,0.3)",
    borderTopColor: "#FFFFFF",
    borderRadius: "50%",
    animation: "spin 0.8s linear infinite",
  },
  loadingText: {
    color: "#FFFFFF",
    marginTop: "16px",
    fontSize: "14px",
  },
  emptyContainer: {
    background: "#FFFFFF",
    borderRadius: "24px",
    padding: "48px",
    textAlign: "center",
    boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
  },
  emptyIcon: {
    color: "#F26522",
    marginBottom: "16px",
  },
  emptyText: {
    color: "#1A1A1A",
    fontSize: "16px",
    fontWeight: 500,
    margin: 0,
  },
  emptySubtext: {
    color: "#6C757D",
    fontSize: "13px",
    margin: "8px 0 0 0",
  },
  requestsContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  requestCard: {
    background: "#FFFFFF",
    borderRadius: "20px",
    padding: "20px",
    boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
    transition: "transform 0.2s, box-shadow 0.2s",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "12px",
  },
  cardHeaderLeft: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  agentIcon: {
    fontSize: "20px",
  },
  agentName: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#1A1A1A",
  },
  statusBadge: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "12px",
    color: "#f59e0b",
    background: "#FEF3C7",
    padding: "4px 12px",
    borderRadius: "20px",
  },
  statusDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#f59e0b",
  },
  requestContext: {
    fontSize: "13px",
    color: "#4B5563",
    lineHeight: 1.5,
    margin: "0 0 16px 0",
    paddingLeft: "30px",
  },
  cardActions: {
    display: "flex",
    gap: "12px",
    paddingLeft: "30px",
  },
  buttonApprove: {
    padding: "8px 20px",
    borderRadius: "30px",
    border: "none",
    background: "#22c55e",
    color: "#FFFFFF",
    fontSize: "13px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  buttonReject: {
    padding: "8px 20px",
    borderRadius: "30px",
    border: "none",
    background: "#ef4444",
    color: "#FFFFFF",
    fontSize: "13px",
    fontWeight: 500,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  buttonDisabled: {
    padding: "8px 20px",
    borderRadius: "30px",
    border: "none",
    background: "#CCCCCC",
    color: "#666666",
    fontSize: "13px",
    fontWeight: 500,
    cursor: "not-allowed",
  },
};

// Ajouter l'animation CSS et le hover
const styleSheet = document.createElement("style");
styleSheet.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .request-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  }
  button:hover {
    transform: scale(1.02);
  }
`;
document.head.appendChild(styleSheet);
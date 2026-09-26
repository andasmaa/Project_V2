import React, { useState, useEffect } from "react";

const COLORS = {
  primary: "#F26522",      // Orange AWB
  primaryLight: "#FF8C42", // Orange clair
  dark: "#1A1A1A",         // Noir
  light: "#FFFFFF",        // Blanc
  grayLight: "#F8F9FA",    // Gris très clair
  gray: "#6C757D",         // Gris moyen
  grayDark: "#343A40",     // Gris foncé
};

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("http://localhost:8000/audit/logs")
      .then(response => response.json())
      .then(data => {
        console.log("📊 Données reçues:", data);
        console.log("📊 Nombre de logs:", data.logs?.length);
        
        if (data.logs && data.logs.length > 0) {
          setLogs(data.logs);
        } else {
          setLogs([]);
        }
        setError(null);
      })
      .catch(err => {
        console.error("❌ Erreur:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.loadingSpinner}></div>
        <p style={styles.loadingText}>Chargement des logs...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <p style={styles.errorText}>Erreur: {error}</p>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>Journal d'audit</h1>
        <p style={styles.subtitle}>Historique des interactions bancaires</p>
      </div>
      
      {logs.length === 0 ? (
        <div style={styles.emptyContainer}>
          <p style={styles.emptyText}>Aucun log trouvé</p>
        </div>
      ) : (
        <div style={styles.tableContainer}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Niveau</th>
                <th style={styles.th}>Message</th>
                <th style={styles.th}>Date</th>
              </tr>
            </thead>
            <tbody>
              {logs.slice().reverse().map((log, i) => (
                <tr key={log.id || i} style={styles.tr}>
                  <td style={styles.td}>
                    <span style={{
                      ...styles.levelBadge,
                      background: log.level === "ERROR" ? "#dc2626" : COLORS.primary,
                    }}>
                      {log.level || "INFO"}
                    </span>
                  </td>
                  <td style={styles.tdMessage}>
                    {log.message?.substring(0, 120)}...
                  </td>
                  <td style={styles.tdDate}>
                    {log.timestamp ? new Date(log.timestamp).toLocaleString() : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
  tableContainer: {
    background: "#FFFFFF",
    borderRadius: "20px",
    overflow: "hidden",
    boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    padding: "16px 16px",
    textAlign: "left",
    background: "#F8F9FA",
    color: "#1A1A1A",
    fontWeight: 600,
    fontSize: "14px",
    borderBottom: "1px solid #E9ECEF",
  },
  tr: {
    borderBottom: "1px solid #F0F0F0",
    transition: "background 0.2s",
  },
  td: {
    padding: "12px 16px",
    verticalAlign: "middle",
  },
  tdMessage: {
    padding: "12px 16px",
    color: "#1A1A1A",
    fontSize: "13px",
    lineHeight: 1.5,
    verticalAlign: "middle",
  },
  tdDate: {
    padding: "12px 16px",
    color: "#6C757D",
    fontSize: "12px",
    whiteSpace: "nowrap",
    verticalAlign: "middle",
  },
  levelBadge: {
    padding: "4px 12px",
    borderRadius: "20px",
    fontSize: "11px",
    fontWeight: 600,
    color: "#FFFFFF",
    display: "inline-block",
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
  errorContainer: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #F26522 0%, #FF8C42 100%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  errorText: {
    color: "#FFFFFF",
    fontSize: "14px",
    textAlign: "center",
  },
  emptyContainer: {
    background: "#FFFFFF",
    borderRadius: "20px",
    padding: "48px",
    textAlign: "center",
  },
  emptyText: {
    color: "#6C757D",
    fontSize: "14px",
    margin: 0,
  },
};

// Ajouter l'animation CSS
const styleSheet = document.createElement("style");
styleSheet.textContent = `
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  tr:hover {
    background: #F8F9FA;
  }
`;
document.head.appendChild(styleSheet);
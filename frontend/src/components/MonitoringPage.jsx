// frontend/src/components/MonitoringPage.jsx
import React, { useState, useEffect, useRef } from 'react';

const API = "http://localhost:8000";
const REFRESH_INTERVAL = 5000;

const MonitoringPage = () => {
  const [authStats, setAuthStats] = useState(null);
  const [authEvents, setAuthEvents] = useState(null);
  const [sessions, setSessions] = useState(null);
  const [suspicious, setSuspicious] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [activeSection, setActiveSection] = useState('overview');
  const [lastUpdate, setLastUpdate] = useState(null);
  const intervalRef = useRef(null);

  const loadAll = async (silent = false) => {
    if (!silent) setIsLoading(true);
    setError('');
    try {
      const [st, ev, se, su] = await Promise.all([
        fetch(`${API}/admin/siem/auth-stats`).then(r => r.json()),
        fetch(`${API}/admin/siem/auth-events?limit=50`).then(r => r.json()),
        fetch(`${API}/admin/siem/sessions`).then(r => r.json()),
        fetch(`${API}/admin/siem/suspicious`).then(r => r.json()),
      ]);
      setAuthStats(st);
      setAuthEvents(ev);
      setSessions(se);
      setSuspicious(su);
      setLastUpdate(new Date().toLocaleTimeString('fr-FR'));
    } catch (err) {
      console.error(" SIEM error:", err);
      setError("Impossible de charger les données SIEM. Backend démarré ?");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    intervalRef.current = setInterval(() => loadAll(true), REFRESH_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh]);

  if (isLoading) {
    return <div style={styles.page}><p style={styles.loading}>Chargement SIEM...</p></div>;
  }

  return (
    <div style={styles.page}>
      {/* HEADER */}
      <div style={styles.header}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h1 style={styles.headerTitle}>Monitoring Authentification (SIEM)</h1>
            <p style={styles.headerSubtitle}>
              Logins, sessions, cookies, IPs, activités suspectes
              {lastUpdate && <span style={{ marginLeft: 10, opacity: 0.8 }}>· MAJ : {lastUpdate}</span>}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              style={{ ...styles.refreshBtn, background: autoRefresh ? '#22c55e' : '#6b7280' }}
            >
              {autoRefresh ? '● Live ON' : '○ Live OFF'}
            </button>
            <button onClick={() => loadAll()} style={styles.refreshBtn}>Rafraîchir</button>
          </div>
        </div>
      </div>

      <div style={styles.container}>
        {error && <div style={styles.errorBox}>{error}</div>}

        {/* ALERTE GLOBALE */}
        {suspicious?.total_alerts > 0 && (
          <div style={styles.alertBox}>
             <b>{suspicious.total_alerts} alerte(s) de sécurité détectée(s)</b> — voir onglet "Suspectes"
          </div>
        )}

        {/* STATS */}
        <div style={styles.statsGrid}>
          <StatCard label="Logins réussis (24h)" value={authStats?.login_success || 0} accent="#10b981" />
          <StatCard label="Logins échoués (24h)" value={authStats?.login_failed || 0} accent="#dc2626" />
          <StatCard label="Logouts (24h)" value={authStats?.logout || 0} accent="#3b82f6" />
          <StatCard label="Taux succès" value={`${authStats?.success_rate || 0}%`} accent="#22c55e" />
          <StatCard label="Sessions actives" value={sessions?.total_sessions || 0} accent="#F26522" />
          <StatCard label="Sessions stale" value={sessions?.stale_sessions || 0} accent="#f59e0b" />
        </div>

        {/* TABS */}
        <div style={styles.tabs}>
          {[
            { id: 'overview', label: 'Vue d\'ensemble' },
            { id: 'events', label: 'Événements auth' },
            { id: 'sessions', label: 'Sessions & cookies' },
            { id: 'suspicious', label: 'Activités suspectes' },
          ].map(t => (
            <button
              key={t.id}
              onClick={() => setActiveSection(t.id)}
              style={{ ...styles.tab, ...(activeSection === t.id ? styles.tabActive : {}) }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div style={styles.section}>

          {/* OVERVIEW */}
          {activeSection === 'overview' && (
            <div>
              <h2 style={styles.sectionTitle}>Résumé sécurité 24h</h2>
              <table style={styles.table}>
                <tbody>
                  <Row label="Total événements" value={authStats?.total_events} />
                  <Row label="Logins réussis" value={authStats?.login_success} color="#10b981" />
                  <Row label="Logins échoués" value={authStats?.login_failed} color="#dc2626" />
                  <Row label="Taux de succès" value={`${authStats?.success_rate}%`} />
                  <Row label="Sessions actives (< 24h)" value={sessions?.active_24h} />
                  <Row label="Sessions stale (> 48h)" value={sessions?.stale_sessions} color="#f59e0b" />
                  <Row label="Alertes suspectes" value={suspicious?.total_alerts} color={suspicious?.total_alerts > 0 ? '#dc2626' : '#10b981'} />
                </tbody>
              </table>
            </div>
          )}

          {/* EVENTS */}
          {activeSection === 'events' && authEvents && (
            <div>
              <h2 style={styles.sectionTitle}>
                Derniers événements d'authentification
                <span style={styles.countBadge}>{authEvents.total}</span>
              </h2>
              {authEvents.events.length === 0 ? (
                <p style={styles.empty}>Aucun événement. Essayez de vous connecter / déconnecter.</p>
              ) : (
                <table style={styles.table}>
                  <thead><tr>
                    <th style={styles.th}>Timestamp</th>
                    <th style={styles.th}>Type</th>
                    <th style={styles.th}>Email</th>
                    <th style={styles.th}>IP</th>
                    <th style={styles.th}>Détails</th>
                  </tr></thead>
                  <tbody>
                    {authEvents.events.map((e, i) => (
                      <tr key={i}>
                        <td style={styles.td}><code style={styles.code}>{e.timestamp}</code></td>
                        <td style={styles.td}>
                          <span style={{ ...styles.badge, ...eventBadge(e.event_type) }}>
                            {e.event_type}
                          </span>
                        </td>
                        <td style={styles.td}>{e.email || '—'}</td>
                        <td style={styles.td}><code style={styles.code}>{e.ip_address || '—'}</code></td>
                        <td style={styles.td}>{e.details || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* SESSIONS */}
          {activeSection === 'sessions' && sessions && (
            <div>
              <h2 style={styles.sectionTitle}>
                Sessions actives
                <span style={styles.countBadge}>{sessions.total_sessions}</span>
              </h2>

              {sessions.alerts.length > 0 && (
                <div style={styles.alertList}>
                  {sessions.alerts.map((a, i) => <div key={i} style={styles.alertItem}>{a}</div>)}
                </div>
              )}

              <table style={styles.table}>
                <thead><tr>
                  <th style={styles.th}>Session</th>
                  <th style={styles.th}>Client</th>
                  <th style={styles.th}>Email</th>
                  <th style={styles.th}>Login</th>
                  <th style={styles.th}>Dernière activité</th>
                  <th style={styles.th}>Âge</th>
                </tr></thead>
                <tbody>
                  {sessions.sessions.map((s, i) => (
                    <tr key={i}>
                      <td style={styles.td}><code style={styles.code}>{s.session_id?.substring(0, 8)}...</code></td>
                      <td style={styles.td}><b>{s.client_name || '—'}</b></td>
                      <td style={styles.td}>{s.email || '—'}</td>
                      <td style={styles.td}><small>{s.login_time}</small></td>
                      <td style={styles.td}><small>{s.last_activity}</small></td>
                      <td style={styles.td}>
                        <span style={{
                          ...styles.badge,
                          background: s.age_hours > 48 ? '#fee2e2' : '#d1fae5',
                          color: s.age_hours > 48 ? '#991b1b' : '#065f46'
                        }}>
                          {s.age_hours != null ? `${s.age_hours}h` : '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* SUSPICIOUS */}
          {activeSection === 'suspicious' && suspicious && (
            <div>
              <h2 style={styles.sectionTitle}>Activités suspectes</h2>

              <h3 style={styles.subTitle}> Multiples échecs (≥ 3 sur 1h)</h3>
              {suspicious.failed_login_alerts.length === 0 ? (
                <p style={styles.empty}>Aucun échec répété.</p>
              ) : (
                <table style={styles.table}>
                  <thead><tr>
                    <th style={styles.th}>Email</th>
                    <th style={styles.th}>Échecs</th>
                  </tr></thead>
                  <tbody>
                    {suspicious.failed_login_alerts.map((a, i) => (
                      <tr key={i}>
                        <td style={styles.td}>{a.email}</td>
                        <td style={styles.td}>
                          <span style={{ ...styles.badge, background: '#fee2e2', color: '#991b1b' }}>
                            {a.failures} échecs
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <h3 style={{ ...styles.subTitle, marginTop: 32 }}>🌍 Connexions multi-IP (≥ 2 IPs / 24h)</h3>
              {suspicious.multi_ip_alerts.length === 0 ? (
                <p style={styles.empty}>Aucune connexion multi-IP.</p>
              ) : (
                <table style={styles.table}>
                  <thead><tr>
                    <th style={styles.th}>Email</th>
                    <th style={styles.th}># IPs</th>
                    <th style={styles.th}>IPs</th>
                  </tr></thead>
                  <tbody>
                    {suspicious.multi_ip_alerts.map((a, i) => (
                      <tr key={i}>
                        <td style={styles.td}>{a.email}</td>
                        <td style={styles.td}><b>{a.ip_count}</b></td>
                        <td style={styles.td}><code style={styles.code}>{a.ips}</code></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

        </div>
      </div>
    </div>
  );
};

// ============ HELPERS ============
const StatCard = ({ label, value, accent }) => (
  <div style={{ ...styles.statCard, borderLeftColor: accent }}>
    <h3 style={styles.statLabel}>{label}</h3>
    <div style={styles.statValue}>{value}</div>
  </div>
);

const Row = ({ label, value, color }) => (
  <tr>
    <td style={styles.td}>{label}</td>
    <td style={styles.td}><b style={{ color: color || '#1A1A1A' }}>{value ?? '—'}</b></td>
  </tr>
);

const eventBadge = (type) => {
  if (type === 'LOGIN_SUCCESS') return { background: '#d1fae5', color: '#065f46' };
  if (type === 'LOGIN_FAILED')  return { background: '#fee2e2', color: '#991b1b' };
  if (type === 'LOGOUT')        return { background: '#dbeafe', color: '#1e40af' };
  return { background: '#f3f4f6', color: '#374151' };
};

// ============ STYLES ============
const styles = {
  page: { minHeight: 'calc(100vh - 60px)', background: '#F9FAFB', fontFamily: "'Segoe UI', Arial, sans-serif" },
  header: { background: 'linear-gradient(135deg, #0f172a 0%, #334155 100%)', color: 'white', padding: '24px 32px' },
  headerTitle: { margin: '0 0 4px 0', fontSize: 22, fontWeight: 600 },
  headerSubtitle: { margin: 0, opacity: 0.9, fontSize: 13 },
  refreshBtn: { padding: '8px 16px', background: '#F26522', color: 'white', border: 'none', borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' },
  container: { padding: '24px 32px', maxWidth: 1400, margin: '0 auto' },
  loading: { color: '#6C757D', fontStyle: 'italic', textAlign: 'center', padding: 60 },
  errorBox: { background: '#fee2e2', color: '#991b1b', padding: '12px 16px', borderRadius: 8, marginBottom: 20, fontSize: 14 },
  alertBox: { background: '#fef3c7', border: '1px solid #f59e0b', color: '#92400e', padding: '14px 18px', borderRadius: 8, marginBottom: 20, fontSize: 14 },

  statsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 },
  statCard: { background: 'white', borderRadius: 12, padding: 18, boxShadow: '0 2px 8px rgba(0,0,0,0.05)', borderLeft: '4px solid #F26522' },
  statLabel: { margin: '0 0 8px 0', fontSize: 12, color: '#6C757D', textTransform: 'uppercase' },
  statValue: { fontSize: 26, fontWeight: 700, color: '#1A1A1A' },

  tabs: { display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' },
  tab: { padding: '8px 16px', background: '#f3f4f6', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 500, fontSize: 13, fontFamily: 'inherit' },
  tabActive: { background: '#F26522', color: 'white' },

  section: { background: 'white', borderRadius: 12, padding: 24, boxShadow: '0 2px 8px rgba(0,0,0,0.05)' },
  sectionTitle: { margin: '0 0 16px 0', fontSize: 18, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 10 },
  subTitle: { margin: '0 0 12px 0', fontSize: 15, fontWeight: 600, color: '#1A1A1A' },
  countBadge: { background: '#F26522', color: 'white', borderRadius: 12, padding: '2px 10px', fontSize: 12, fontWeight: 700 },

  table: { width: '100%', borderCollapse: 'collapse' },
  th: { background: '#f3f4f6', textAlign: 'left', padding: 12, fontSize: 12, textTransform: 'uppercase', color: '#6C757D', fontWeight: 600 },
  td: { padding: 12, borderTop: '1px solid #f3f4f6', fontSize: 13 },

  badge: { display: 'inline-block', padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600 },
  code: { background: '#f3f4f6', padding: '2px 6px', borderRadius: 4, fontSize: 11, fontFamily: 'monospace' },

  alertList: { marginBottom: 16 },
  alertItem: { background: '#fef3c7', color: '#92400e', padding: '10px 14px', borderRadius: 6, fontSize: 13, marginBottom: 6 },

  empty: { color: '#9CA3AF', fontStyle: 'italic', padding: 20, textAlign: 'center', fontSize: 13 },
};

export default MonitoringPage;
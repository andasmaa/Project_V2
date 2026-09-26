// frontend/src/components/RAGPage.jsx
import React, { useState, useEffect } from 'react';

const API = "http://localhost:8000";

const RAGPage = () => {
  // ========== STATE ==========
  const [stats, setStats] = useState(null);
  const [collections, setCollections] = useState(null);
  const [agents, setAgents] = useState(null);

  const [currentCollection, setCurrentCollection] = useState('public');

  const [query, setQuery] = useState('');
  const [userRole, setUserRole] = useState('client');
  const [agentFilter, setAgentFilter] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // ========== CHARGEMENT INITIAL ==========
  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setIsLoading(true);
    setError('');
    try {
      const [statsRes, colRes, agRes] = await Promise.all([
        fetch(`${API}/admin/rag/stats`).then(r => r.json()),
        fetch(`${API}/admin/rag/collections`).then(r => r.json()),
        fetch(`${API}/admin/rag/agents`).then(r => r.json()),
      ]);
      setStats(statsRes);
      setCollections(colRes);
      setAgents(agRes);
    } catch (err) {
      console.error("Erreur chargement RAG:", err);
      setError("Impossible de charger les données RAG. Vérifiez que le backend est démarré.");
    } finally {
      setIsLoading(false);
    }
  };

  // ========== RECHERCHE ==========
  const runSearch = async () => {
    if (!query.trim()) {
      alert("Entrez une question.");
      return;
    }
    setIsSearching(true);
    setSearchResults(null);

    try {
      const res = await fetch(`${API}/admin/rag/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          k: 5,
          user_role: userRole,
          agent_filter: agentFilter || null,
        }),
      });
      const data = await res.json();
      setSearchResults(data);
    } catch (err) {
      console.error(err);
      setSearchResults({ error: "Erreur lors de la recherche." });
    } finally {
      setIsSearching(false);
    }
  };

  // ========== HELPERS ==========
  const badgeClass = (level) => {
    if (level === 'public') return styles.badgePublic;
    if (level === 'confidential') return styles.badgeConfidential;
    if (level === 'secret') return styles.badgeSecret;
    return styles.badgeType;
  };

  // ========== RENDER ==========
  if (isLoading) {
    return (
      <div style={styles.loadingContainer}>
        <p style={styles.loadingText}>Chargement du RAG...</p>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      {/* ========== HEADER ========== */}
      <div style={styles.header}>
        <h1 style={styles.headerTitle}> RAG Administration</h1>
        <p style={styles.headerSubtitle}>
          ChromaDB multi-collections · all-MiniLM-L6-v2 · Isolation par niveau de sensibilité
        </p>
      </div>

      <div style={styles.container}>
        {error && <div style={styles.errorBox}>{error}</div>}

        {/* ========== STATS CARDS ========== */}
        <div style={styles.statsGrid}>
          <StatCard
            label="Total documents"
            value={stats?.total_documents || 0}
          />
          <StatCard
            label=" Public"
            value={stats?.collections?.public || 0}
            accent="#10b981"
          />
          <StatCard
            label=" Confidentiel"
            value={stats?.collections?.confidential || 0}
            accent="#f59e0b"
          />
          <StatCard
            label=" Secret"
            value={stats?.collections?.secret || 0}
            accent="#dc2626"
          />
          <StatCard
            label="Modèle"
            value={stats?.model || "—"}
            small
          />
        </div>

        {/* ========== RECHERCHE SÉMANTIQUE ========== */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}> Recherche sémantique interactive</h2>

          <div style={styles.searchForm}>
            <input
              type="text"
              placeholder="Ex : crédit immobilier, opposition carte, fraude..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runSearch()}
              style={styles.input}
            />

            <select
              value={userRole}
              onChange={(e) => setUserRole(e.target.value)}
              style={styles.select}
            >
              <option value="client">Rôle : client</option>
              <option value="supervisor">Rôle : supervisor</option>
              <option value="admin">Rôle : admin</option>
            </select>

            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              style={styles.select}
            >
              <option value="">Agent : aucun</option>
              <option value="AG01">AG01 - Modérateur</option>
              <option value="AG03">AG03 - Réclamations</option>
              <option value="AG04">AG04 - Info comptes</option>
              <option value="AG06">AG06 - Crédit</option>
              <option value="AG08">AG08 - Opposition</option>
              <option value="AG09">AG09 - Fraude</option>
              <option value="AG10">AG10 - Clôture</option>
              <option value="AG11">AG11 - Succession</option>
              <option value="AG13">AG13 - RGPD</option>
              <option value="AG14">AG14 - Audit</option>
            </select>

            <button
              onClick={runSearch}
              disabled={isSearching}
              style={{
                ...styles.buttonPrimary,
                background: isSearching ? '#cccccc' : '#F26522',
                cursor: isSearching ? 'not-allowed' : 'pointer',
              }}
            >
              {isSearching ? 'Recherche...' : 'Rechercher'}
            </button>
          </div>

          {/* Résultats de recherche */}
          {searchResults && <SearchResults data={searchResults} badgeClass={badgeClass} />}
        </div>

        {/* ========== MATRICE DES PERMISSIONS ========== */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}> Matrice des permissions agents × collections</h2>
          <div style={styles.tableWrapper}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Agent</th>
                  <th style={styles.th}>Niveau</th>
                  <th style={styles.th}>Collections accessibles</th>
                </tr>
              </thead>
              <tbody>
                {agents?.agents?.map((a) => (
                  <tr key={a.agent_id}>
                    <td style={styles.td}><b>{a.agent_id}</b></td>
                    <td style={styles.td}>
                      <span style={{ ...styles.badge, ...badgeClass(a.security_level) }}>
                        {a.security_level}
                      </span>
                    </td>
                    <td style={styles.td}>
                      {a.allowed_collections.map((c) => (
                        <span
                          key={c}
                          style={{ ...styles.badge, ...badgeClass(c), marginRight: 4 }}
                        >
                          {c}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ========== COLLECTIONS ========== */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}> Documents par collection</h2>

          <div style={styles.tabs}>
            {["public", "confidential", "secret"].map((level) => {
              const col = collections?.collections?.[level];
              if (!col) return null;
              const labels = { public: " Public", confidential: " Confidentiel", secret: " Secret" };
              const isActive = currentCollection === level;
              return (
                <button
                  key={level}
                  onClick={() => setCurrentCollection(level)}
                  style={{
                    ...styles.tab,
                    ...(isActive ? styles.tabActive : {}),
                  }}
                >
                  {labels[level]} ({col.count})
                </button>
              );
            })}
          </div>

          <CollectionView
            collection={collections?.collections?.[currentCollection]}
            level={currentCollection}
            badgeClass={badgeClass}
          />
        </div>
      </div>
    </div>
  );
};

// =====================================================
// SOUS-COMPOSANTS
// =====================================================

const StatCard = ({ label, value, accent, small }) => (
  <div style={{ ...styles.statCard, borderLeftColor: accent || '#F26522' }}>
    <h3 style={styles.statLabel}>{label}</h3>
    <div style={{ ...styles.statValue, fontSize: small ? 16 : 28 }}>
      {value}
    </div>
  </div>
);

const CollectionView = ({ collection, level, badgeClass }) => {
  if (!collection || collection.count === 0) {
    return <p style={styles.empty}>Aucun document dans cette collection.</p>;
  }

  return (
    <div>
      <p style={styles.collectionInfo}>
        Collection <b>{collection.name}</b> — {collection.count} document(s)
      </p>
      {collection.documents.map((doc) => {
        const meta = doc.metadata || {};
        return (
          <div key={doc.id} style={styles.docItem}>
            <div style={styles.docHeader}>
              <span style={styles.docId}>{doc.id}</span>
              <span style={{ ...styles.badge, ...badgeClass(level) }}>
                {level}
              </span>
            </div>
            <div style={styles.docContent}>{doc.content}</div>
            <div style={styles.docMeta}>
              {meta.agent && (
                <span style={{ ...styles.badge, ...styles.badgeAgent }}>
                  {meta.agent}
                </span>
              )}
              {meta.topic && (
                <span style={{ ...styles.badge, ...styles.badgeTopic }}>
                  {meta.topic}
                </span>
              )}
              {meta.type && (
                <span style={{ ...styles.badge, ...styles.badgeType }}>
                  {meta.type}
                </span>
              )}
              {meta.nom && (
                <span style={{ ...styles.badge, ...styles.badgeType }}>
                  📄 {meta.nom}
                </span>
              )}
              <span style={{ ...styles.badge, ...styles.badgeType }}>
                {doc.content_length} chars
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

const SearchResults = ({ data, badgeClass }) => {
  if (data.error) {
    return <p style={styles.empty}>{data.error}</p>;
  }

  return (
    <div>
      <p style={styles.searchInfo}>
        Rôle : <b>{data.user_role}</b> · Agent : <b>{data.agent_filter || 'aucun'}</b> ·
        Collections interrogées :{" "}
        {data.allowed_collections.map((c) => (
          <span key={c} style={{ ...styles.badge, ...badgeClass(c), marginLeft: 4 }}>
            {c}
          </span>
        ))}{" "}
        · Seuil : {data.threshold}
      </p>

      {data.results.length === 0 && (
        <p style={styles.empty}>Aucun résultat (vérifiez le rôle ou l'agent).</p>
      )}

      {data.results.map((r, idx) => {
        const meta = r.metadata || {};
        const kept = r.kept;
        return (
          <div
            key={idx}
            style={{
              ...styles.resultItem,
              borderLeftColor: kept ? '#10b981' : '#dc2626',
              background: kept ? '#f0fdf4' : '#fef2f2',
              opacity: kept ? 1 : 0.7,
            }}
          >
            <div style={styles.resultHeader}>
              <span style={styles.resultScore}>
                score = {r.score} {kept ? '' : ' (rejeté)'}
              </span>
              <span style={{ ...styles.badge, ...badgeClass(r.security_level) }}>
                {r.security_level}
              </span>
              <span style={styles.docId}>{r.id}</span>
            </div>
            <div style={styles.docContent}>
              {r.content.substring(0, 500)}
              {r.content.length > 500 ? "..." : ""}
            </div>
            <div style={styles.docMeta}>
              {meta.agent && (
                <span style={{ ...styles.badge, ...styles.badgeAgent }}>{meta.agent}</span>
              )}
              {meta.topic && (
                <span style={{ ...styles.badge, ...styles.badgeTopic }}>{meta.topic}</span>
              )}
              {meta.type && (
                <span style={{ ...styles.badge, ...styles.badgeType }}>{meta.type}</span>
              )}
              <span style={{ ...styles.badge, ...styles.badgeType }}>
                distance = {r.distance}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

// =====================================================
// STYLES (inline — cohérents avec LoginPage)
// =====================================================
const styles = {
  page: {
    minHeight: '100vh',
    background: '#F9FAFB',
    fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
  },
  header: {
    background: 'linear-gradient(135deg, #F26522 0%, #d9541a 100%)',
    color: 'white',
    padding: '24px 32px',
  },
  headerTitle: {
    margin: '0 0 4px 0',
    fontSize: 22,
    fontWeight: 600,
  },
  headerSubtitle: {
    margin: 0,
    opacity: 0.9,
    fontSize: 13,
  },
  container: {
    padding: '24px 32px',
    maxWidth: 1400,
    margin: '0 auto',
  },
  loadingContainer: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', sans-serif",
  },
  loadingText: {
    color: '#6C757D',
    fontStyle: 'italic',
  },
  errorBox: {
    background: '#fee2e2',
    color: '#991b1b',
    padding: '12px 16px',
    borderRadius: 8,
    marginBottom: 20,
    fontSize: 14,
  },

  // STATS
  statsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
    gap: 16,
    marginBottom: 24,
  },
  statCard: {
    background: 'white',
    borderRadius: 12,
    padding: 20,
    boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
    borderLeft: '4px solid #F26522',
  },
  statLabel: {
    margin: '0 0 8px 0',
    fontSize: 12,
    color: '#6C757D',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statValue: {
    fontSize: 28,
    fontWeight: 700,
    color: '#1A1A1A',
  },

  // SECTION
  section: {
    background: 'white',
    borderRadius: 12,
    padding: 24,
    boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
    marginBottom: 24,
  },
  sectionTitle: {
    margin: '0 0 16px 0',
    fontSize: 18,
    fontWeight: 600,
  },

  // SEARCH
  searchForm: {
    display: 'grid',
    gridTemplateColumns: '2fr 1fr 1fr auto',
    gap: 10,
    marginBottom: 16,
  },
  input: {
    padding: '10px 14px',
    border: '1px solid #E0E0E0',
    borderRadius: 8,
    fontSize: 14,
    fontFamily: 'inherit',
    outline: 'none',
    background: '#F9FAFB',
  },
  select: {
    padding: '10px 14px',
    border: '1px solid #E0E0E0',
    borderRadius: 8,
    fontSize: 14,
    fontFamily: 'inherit',
    outline: 'none',
    background: '#F9FAFB',
  },
  buttonPrimary: {
    padding: '10px 20px',
    background: '#F26522',
    color: 'white',
    border: 'none',
    borderRadius: 8,
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    fontSize: 14,
  },

  // TABS
  tabs: {
    display: 'flex',
    gap: 8,
    marginBottom: 16,
    flexWrap: 'wrap',
  },
  tab: {
    padding: '8px 16px',
    background: '#f3f4f6',
    border: 'none',
    borderRadius: 8,
    cursor: 'pointer',
    fontWeight: 500,
    fontSize: 13,
    fontFamily: 'inherit',
  },
  tabActive: {
    background: '#F26522',
    color: 'white',
  },

  // DOCS
  docItem: {
    border: '1px solid #E5E7EB',
    borderRadius: 8,
    padding: 14,
    marginBottom: 10,
    background: '#FAFAFA',
  },
  docHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  docId: {
    fontFamily: 'monospace',
    fontSize: 12,
    color: '#6C757D',
  },
  docContent: {
    fontSize: 13,
    color: '#374151',
    lineHeight: 1.5,
    whiteSpace: 'pre-wrap',
  },
  docMeta: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    marginTop: 10,
  },
  collectionInfo: {
    fontSize: 13,
    color: '#6C757D',
    margin: '0 0 12px 0',
  },

  // BADGES
  badge: {
    display: 'inline-block',
    padding: '3px 10px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 600,
  },
  badgePublic: { background: '#d1fae5', color: '#065f46' },
  badgeConfidential: { background: '#fef3c7', color: '#92400e' },
  badgeSecret: { background: '#fee2e2', color: '#991b1b' },
  badgeAgent: { background: '#dbeafe', color: '#1e40af' },
  badgeTopic: { background: '#ede9fe', color: '#5b21b6' },
  badgeType: { background: '#f3f4f6', color: '#374151' },

  // RESULTS
  searchInfo: {
    fontSize: 13,
    color: '#6C757D',
    margin: '0 0 12px 0',
  },
  resultItem: {
    borderLeft: '4px solid #F26522',
    padding: 14,
    borderRadius: 8,
    marginBottom: 10,
  },
  resultHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
    flexWrap: 'wrap',
  },
  resultScore: {
    fontWeight: 700,
    color: '#F26522',
    fontSize: 14,
    marginRight: 'auto',
  },

  // TABLE
  tableWrapper: {
    overflowX: 'auto',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  th: {
    background: '#f3f4f6',
    textAlign: 'left',
    padding: 10,
    fontSize: 12,
    textTransform: 'uppercase',
    color: '#6C757D',
  },
  td: {
    padding: 10,
    borderTop: '1px solid #f3f4f6',
    fontSize: 13,
  },

  // EMPTY
  empty: {
    color: '#9CA3AF',
    fontStyle: 'italic',
    padding: 20,
    textAlign: 'center',
  },
};

export default RAGPage;
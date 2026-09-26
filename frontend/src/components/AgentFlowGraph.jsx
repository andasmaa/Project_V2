// components/AgentFlowGraph.jsx
import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import ReactFlow, { Background, Controls, MarkerType, useReactFlow, ReactFlowProvider } from 'reactflow';
import 'reactflow/dist/style.css';
import dagre from 'dagre';

const AGENT_NODES = new Set([
  'agent_credit', 'agent_info', 'agent_fraud', 'agent_complaint',
  'agent_incident', 'agent_admin', 'agent_opposition',
  'agent_closure', 'agent_succession', 'agent_rgpd'
]);

const COLORS = {
  agent:  { bg: '#FAECE7', border: '#D85A30', text: '#4A1B0C' },
  hitl:   { bg: '#FAEEDA', border: '#BA7517', text: '#412402' },
  active: { bg: '#F26522', border: '#1A1A1A', text: '#ffffff' },
  visited:{ bg: '#EAF3DE', border: '#639922', text: '#173404' },
  infra:  { bg: '#ffffff', border: '#1A1A1A', text: '#1A1A1A' },
};

function getLayoutedElements(nodes, edges) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'TB', nodesep: 40, ranksep: 60 });
  nodes.forEach(n => g.setNode(n.id, { width: 150, height: 44 }));
  edges.forEach(e => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return nodes.map(n => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - 75, y: pos.y - 22 } };
  });
}

// 🔥 Badges de sécurité affichés directement sur le node
function securityBadges(security = {}) {
  const b = [];
  if (security.is_toxic) b.push('⚠️');
  if (security.rgpd_check_passed) b.push('🛡️');
  if (security.pii_detected?.length) b.push('🔒');
  if (security.requires_hitl) b.push('🔐');
  return b.join(' ');
}

function styleFor(nodeId, state) {
  const c = state === 'active' ? COLORS.active
          : state === 'visited' ? COLORS.visited
          : AGENT_NODES.has(nodeId) ? COLORS.agent
          : nodeId === 'hitl_gate' ? COLORS.hitl
          : COLORS.infra;
  return {
    background: c.bg, border: `1.5px solid ${c.border}`, color: c.text,
    borderRadius: 8, fontSize: 11, fontWeight: 500, padding: '6px 8px',
    width: 150, textAlign: 'center', transition: 'all 0.25s ease',
    cursor: 'pointer', whiteSpace: 'pre-line',
  };
}

const WS_URL = 'ws://localhost:8000/ws/graph-execution';
const API_URL = 'http://localhost:8000/api/graph/structure';

// 🔥 Composant interne : appelle fitView à chaque fois que les nodes changent,
// après un court délai pour laisser le conteneur flex se stabiliser avant de zoomer.
function AutoFitView({ nodes }) {
  const { fitView } = useReactFlow();

  useEffect(() => {
    if (nodes.length === 0) return;
    const timer = setTimeout(() => {
      fitView({ padding: 0.15, duration: 300 });
    }, 100);
    return () => clearTimeout(timer);
  }, [nodes, fitView]);

  return null;
}
// 🔥 Surligne le mot-clé détecté dans le texte pseudonymisé
function highlightKeyword(text, keyword) {
  if (!text || !keyword) return text;
  const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark style={{ background: '#FFE08A', padding: '0 2px', borderRadius: 3 }}>
        {text.slice(idx, idx + keyword.length)}
      </mark>
      {text.slice(idx + keyword.length)}
    </>
  );
}

const AgentFlowGraphInner = forwardRef(({ sessionId }, ref) => {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [activeNode, setActiveNode] = useState(null);
  const [visited, setVisited] = useState(new Set());
  const [connected, setConnected] = useState(false);
  const [trace, setTrace] = useState([]);
  const [selectedStep, setSelectedStep] = useState(null);
  const wsRef = useRef(null);
  const clientIdRef = useRef(crypto.randomUUID());
  const nodeDataRef = useRef({});
  const baseLabelsRef = useRef({});

  useEffect(() => {
    fetch(API_URL).then(r => r.json()).then(data => {
      data.nodes.forEach(n => { baseLabelsRef.current[n.id] = n.label; });
      const initialNodes = data.nodes.map(n => ({
        id: n.id, data: { label: n.label }, position: { x: 0, y: 0 },
        style: styleFor(n.id, 'idle'),
      }));
      setNodes(getLayoutedElements(initialNodes, data.edges));
      setEdges(data.edges.map(e => ({
        id: `${e.source}-${e.target}`, source: e.source, target: e.target,
        animated: e.conditional, style: { stroke: '#B4B2A9', strokeWidth: 1 },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#B4B2A9' },
      })));
    }).catch(err => console.error('Erreur structure graphe:', err));
  }, []);

  useEffect(() => {
    const ws = new WebSocket(`${WS_URL}/${clientIdRef.current}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (msg) => {
      const event = JSON.parse(msg.data);
      const now = new Date().toLocaleTimeString('fr-FR');

      if (event.type === 'node_start') {
        setActiveNode(event.node);
        setTrace(prev => [...prev, { ...event, phase: 'start', time: now }]);
      } else if (event.type === 'node_end') {
        setVisited(prev => new Set(prev).add(event.node));
        setActiveNode(null);
        nodeDataRef.current[event.node] = event;
        setTrace(prev => [...prev, { ...event, phase: 'end', time: now }]);
      } else if (event.type === 'done') {
        setTimeout(() => setVisited(new Set()), 4000);
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    setNodes(nds => nds.map(n => {
      const state = n.id === activeNode ? 'active' : visited.has(n.id) ? 'visited' : 'idle';
      const meta = nodeDataRef.current[n.id];
      const badges = meta ? securityBadges(meta.security) : '';
      const base = baseLabelsRef.current[n.id] || n.id;
      return {
        ...n,
        style: styleFor(n.id, state),
        data: { label: badges ? `${base}\n${badges}` : base },
      };
    }));
  }, [activeNode, visited]);

  const onNodeClick = (_, node) => {
    const meta = nodeDataRef.current[node.id];
    setSelectedStep({ node: node.id, ...(meta || {}) });
  };

  useImperativeHandle(ref, () => ({
    sendMessage: (message) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        setVisited(new Set());
        setTrace([]);
        nodeDataRef.current = {};
        setSelectedStep(null);
        wsRef.current.send(JSON.stringify({ message, client_session_id: sessionId }));
      }
    },
  }));

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', gap: 12 }}>
      {/* Graphe */}
      <div style={{ flex: 2, background: '#fff', borderRadius: 20, overflow: 'hidden', position: 'relative' }}>
        <div style={{
          position: 'absolute', top: 12, right: 16, zIndex: 10,
          display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#6C757D',
        }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: connected ? '#22c55e' : '#dc2626' }} />
          {connected ? 'Flux connecté' : 'Déconnecté'}
        </div>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodeClick={onNodeClick}
          minZoom={0.1}
          proOptions={{ hideAttribution: true }}
        >
          <AutoFitView nodes={nodes} />
          <Background color="#F5F5F5" gap={14} />
          <Controls />
        </ReactFlow>
      </div>

      {/* 🔥 Panneau audit / détail */}
      <div style={{ flex: 1, minWidth: 260, background: '#fff', borderRadius: 20, padding: 14, overflowY: 'auto', fontSize: 12 }}>
        <h4 style={{ margin: '0 0 10px 0', color: '#1A1A1A' }}>Journal d'audit (live)</h4>

        {selectedStep ? (
          <div style={{ marginBottom: 16, padding: 10, background: '#F8F9FA', borderRadius: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>{selectedStep.node}</strong>
              <button onClick={() => setSelectedStep(null)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#6C757D' }}>✕</button>
            </div>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 11, marginTop: 6 }}>
              {JSON.stringify(selectedStep.security || {}, null, 2)}
            </pre>
            {selectedStep.security?.routing_explanation && (
              <div style={{ marginTop: 10, padding: 10, background: '#FFF9EC', borderRadius: 8, border: '1px solid #F2CB6E' }}>
                <div style={{ fontWeight: 600, marginBottom: 6, color: '#7A5A00' }}> Explicabilité du routage</div>
                <div style={{ marginBottom: 4 }}>
                  <b>Catégorie :</b> {selectedStep.security.routing_explanation.category_label}
                </div>
                <div style={{ marginBottom: 4 }}>
                  <b>Agent choisi :</b> {selectedStep.security.routing_explanation.target_agent}
                </div>
                {selectedStep.security.routing_explanation.matched_keyword && (
                  <div style={{ marginBottom: 4 }}>
                    <b>Mot-clé déclencheur :</b>{' '}
                    {selectedStep.security.pseudonymized_message
                      ? highlightKeyword(selectedStep.security.pseudonymized_message, selectedStep.security.routing_explanation.matched_keyword)
                      : selectedStep.security.routing_explanation.matched_keyword}
                  </div>
                )}
                <div style={{ fontSize: 11, color: '#6C757D', marginTop: 6 }}>
                  {selectedStep.security.routing_explanation.reasoning}
                </div>
              </div>
            )}
            {selectedStep.target_agent && <div>Agent cible : <b>{selectedStep.target_agent}</b></div>}
            {selectedStep.rag_results_count != null && <div>Documents RAG : {selectedStep.rag_results_count}</div>}
            {!selectedStep.security && !selectedStep.target_agent && (
              <div style={{ color: '#9CA3AF' }}>Pas encore de données pour ce node (pas encore exécuté).</div>
            )}
          </div>
        ) : (
          <p style={{ color: '#9CA3AF' }}>Clique sur un node du flux pour voir le détail de cette étape.</p>
        )}

        <div style={{ borderTop: '1px solid #F0F0F0', paddingTop: 10 }}>
          {trace.map((t, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', color: t.phase === 'start' ? '#9CA3AF' : '#1A1A1A' }}>
              <span>{t.phase === 'start' ? '▶' : '✓'} {t.node}</span>
              <span style={{ fontSize: 10, color: '#B0B0B0' }}>{t.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
});

// 🔥 Wrapper : ReactFlowProvider est requis pour que useReactFlow() (utilisé
// dans AutoFitView) fonctionne à l'intérieur du composant.
const AgentFlowGraph = forwardRef((props, ref) => (
  <ReactFlowProvider>
    <AgentFlowGraphInner {...props} ref={ref} />
  </ReactFlowProvider>
));

export default AgentFlowGraph;
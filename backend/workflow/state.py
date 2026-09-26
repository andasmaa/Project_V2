"""
state.py — État LangGraph AWB
Carnet de bord partagé entre tous les nodes du workflow.
"""

from typing import TypedDict, List, Dict, Optional
from datetime import datetime


class AgentState(TypedDict):
    # ── Identification session ────────────────────────────────────────────
    session_id:   str
    user_id:      str
    timestamp:    datetime

    # ── Message ───────────────────────────────────────────────────────────
    message:               str    # message courant (peut être modifié)
    original_message:      str    # message d'origine non modifié
    pseudonymized_message: str    # version masquant les PII

    # ── Modération ────────────────────────────────────────────────────────
    toxicity_score: float         # 0.0 → 1.0
    is_toxic:       bool

    # ── Routing ───────────────────────────────────────────────────────────
    intent:       str             # credit | info | fraud | complaint | ...
    target_agent: str             # AG04, AG06, AG09, ...
    confidence:   float           # confiance du routeur (0.0 → 1.0)
    routing_explanation: Optional[Dict]  # intent/agent/mot-clé/raisonnement
                                         # renvoyés par router_node — sans
                                         # cette déclaration LangGraph rejette
                                         # la mise à jour d'état de ce node.

    # ── RAG ───────────────────────────────────────────────────────────────
    rag_results:       List[Dict] # documents ChromaDB récupérés
    compressed_context: str       # contexte compressé injecté dans le LLM

    # ── Réponse agent ─────────────────────────────────────────────────────
    agent_response:  str
    confidence_score: float       # confiance de la réponse (0.0 → 1.0)

    # ── HITL ──────────────────────────────────────────────────────────────
    requires_hitl: bool
    hitl_reason:   str            # explication lisible (ex: "Montant > 100k€")

    # ── Sécurité & audit ──────────────────────────────────────────────────
    signatures:         List[str] # signatures Ed25519 des checkpoints
    worm_logs:          List[Dict] # entrées WORM de la session
    rgpd_check_passed:  bool
    pii_detected:       List[str] # liste des PII masqués

    # ── Métadonnées de traçabilité ────────────────────────────────────────
    processing_time: float        # durée totale en secondes
    nodes_visited:   List[str]    # liste ordonnée des nodes traversés
    user_context: Dict

    # ── Gouvernance / audit (ajouté par la couche gouvernance) ─────────────
    workflow_execution_id: str          # ID unique de CETTE exécution du
                                         # graphe — clé de corrélation L1/L2/L3
                                         # (distinct de session_id, qui peut
                                         # couvrir plusieurs exécutions/tours)
    hitl_request_id:   Optional[str]    # ID réel renvoyé par
                                         # HITLGate.request_approval(), au lieu
                                         # d'être perdu comme auparavant
    governance_risk:   Optional[Dict]   # dernière RiskAssessment calculée
                                         # (governance.risk_policy), au format
                                         # RiskAssessment.to_dict()
    pseudonymized_response: Optional[str]  # réponse pseudonymisée (déjà
                                         # utilisée par app.py / le stream
                                         # WebSocket ; formalisée ici)
    judge_evaluation: Optional[Dict]    # résultat brut du Judge LLM
                                         # (factualite, coherence,
                                         # absence_hallucination, score_total,
                                         # decision), écrit par judge_node.
                                         # Sans cette déclaration, LangGraph
                                         # rejette toute la mise à jour d'état
                                         # renvoyée par judge_node.
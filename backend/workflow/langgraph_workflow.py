"""
langgraph_workflow.py — Workflow LangGraph AWB complet
21 nodes · 14 agents · Groq API · ChromaDB RAG · HITL progressif · WORM Audit
"""

from langgraph.graph import StateGraph, END
from typing import Dict
from datetime import datetime
from agents.base_agent import BaseAgent
from workflow.state import AgentState
from agents.judge_agent import JudgeAgent
# ── Agents existants ─────────────────────────────────────────────────────────
from agents.moderation_agent import ModerationAgent
from agents.credit_agent import CreditAgent
from agents.info_agent import InfoAgent

# ── Nouveaux agents métier ───────────────────────────────────────────────────
from agents.agents_metier import (
    ComplaintAgent,
    IncidentAgent,
    AdminAgent,
    OppositionAgent,
    FraudAgent,
    ClosureAgent,
    SuccessionAgent,
    RGPDAgent,
)

# ── Sécurité & RAG ───────────────────────────────────────────────────────────
from security.hitl_gate import HITLGate
from security.worm_audit import WormAudit
from rag.chroma_store import ChromaStore
import re
import time
import uuid

# ── Gouvernance (couche audit/risque/intégrité — observe le workflow) ───────
from governance.audit_service import AuditService
from governance.models import EventType

class BankAgentWorkflow:

    def __init__(self):
        # ── Agents ───────────────────────────────────────────────────────────
        self.moderation_agent = ModerationAgent()
        self.credit_agent = CreditAgent()
        self.info_agent = InfoAgent()
        self.complaint_agent = ComplaintAgent()
        self.incident_agent = IncidentAgent()
        self.admin_agent = AdminAgent()
        self.opposition_agent = OppositionAgent()
        self.fraud_agent = FraudAgent()
        self.closure_agent = ClosureAgent()
        self.succession_agent = SuccessionAgent()
        self.rgpd_agent = RGPDAgent()
        self.judge_agent = JudgeAgent()
        # ── Gouvernance ──────────────────────────────────────────────────────
        # ONE AuditService instance, shared with the WormAudit compatibility
        # wrapper below, so workflow nodes calling AuditService directly and
        # any remaining .write()-style legacy calls land in the exact same
        # audit trail rather than two independently-configured clients.
        self.audit_service = AuditService()
        # ── Sécurité ─────────────────────────────────────────────────────────
        self.hitl_gate = HITLGate(audit_service=self.audit_service)
        self.worm_audit = WormAudit(audit_service=self.audit_service)

        # ── RAG ──────────────────────────────────────────────────────────────
        self.chroma = ChromaStore()

        # ── Graph ────────────────────────────────────────────────────────────
        self.graph = self._build_graph()

    # ═════════════════════════════════════════════════════════════════════════
    # CONSTRUCTION DU GRAPH
    # ═════════════════════════════════════════════════════════════════════════
    def _build_graph(self):
        workflow = StateGraph(AgentState)

        # ── Nodes infrastructure ─────────────────────────────────────────────
        workflow.add_node("entry", self.entry_node)
        workflow.add_node("moderation", self.moderation_node)
        workflow.add_node("router", self.router_node)
        workflow.add_node("rag_retrieve", self.rag_retrieve_node)  # 🔥 AJOUTÉ
        workflow.add_node("output_validator", self.output_validator_node)
        workflow.add_node("hitl_gate", self.hitl_gate_node)
        workflow.add_node("judge", self.judge_node)
        workflow.add_node("end", self.end_node)

        # ── Nodes agents métier ──────────────────────────────────────────────
        workflow.add_node("agent_credit", self.credit_node)
        workflow.add_node("agent_info", self.info_node)
        workflow.add_node("agent_fraud", self.fraud_node)
        workflow.add_node("agent_complaint", self.complaint_node)
        workflow.add_node("agent_incident", self.incident_node)
        workflow.add_node("agent_admin", self.admin_node)
        workflow.add_node("agent_opposition", self.opposition_node)
        workflow.add_node("agent_closure", self.closure_node)
        workflow.add_node("agent_succession", self.succession_node)
        workflow.add_node("agent_rgpd", self.rgpd_node)

        # ── Edges ─────────────────────────────────────────────────────────────
        workflow.set_entry_point("entry")
        workflow.add_edge("entry", "moderation")

        # Après modération : toxic → end  |  safe → router
        workflow.add_conditional_edges(
            "moderation",
            self.route_after_moderation,
            {"toxic": "end", "safe": "router"},
        )

        # Router → RAG → agent cible
        workflow.add_conditional_edges(
            "router",
            self.route_intent,
            {
                "credit": "rag_retrieve",
                "info": "rag_retrieve",
                "fraud": "rag_retrieve",
                "complaint": "rag_retrieve",
                "incident": "rag_retrieve",
                "admin": "rag_retrieve",
                "opposition": "rag_retrieve",
                "closure": "rag_retrieve",
                "succession": "rag_retrieve",
                "rgpd": "rag_retrieve",
                "default": "rag_retrieve",
            },
        )

        # RAG → agent cible
        workflow.add_conditional_edges(
            "rag_retrieve",
            self.route_after_rag,
            {
                "credit": "agent_credit",
                "info": "agent_info",
                "fraud": "agent_fraud",
                "complaint": "agent_complaint",
                "incident": "agent_incident",
                "admin": "agent_admin",
                "opposition": "agent_opposition",
                "closure": "agent_closure",
                "succession": "agent_succession",
                "rgpd": "agent_rgpd",
                "default": "agent_info",
            },
        )

        # Agents avec HITL conditionnel → hitl_gate ou output_validator
        for agent_node in [
            "agent_credit", "agent_fraud", "agent_complaint",
            "agent_incident", "agent_closure", "agent_succession", "agent_rgpd",
        ]:
            workflow.add_conditional_edges(
                agent_node,
                self.route_hitl,
                {"hitl": "hitl_gate", "direct": "output_validator"},
            )

        # Agents sans HITL → direct output_validator
        for agent_node in ["agent_info", "agent_admin", "agent_opposition"]:
            workflow.add_edge(agent_node, "output_validator")

        workflow.add_edge("hitl_gate", "output_validator")
        workflow.add_edge("output_validator", "judge")
        workflow.add_edge("judge", "end")
        workflow.add_edge("end", END)

        return workflow.compile()

    # ═════════════════════════════════════════════════════════════════════════
    # INITIALISATION
    # ═════════════════════════════════════════════════════════════════════════
    async def initialize(self):
        await self.chroma.initialize()
        print("Workflow AWB initialisé — 14 agents | ChromaDB RAG | Groq API")

    # ═════════════════════════════════════════════════════════════════════════
    # POINT D'ENTRÉE PUBLIC
    # ═════════════════════════════════════════════════════════════════════════
    async def process_message(self, message: str, user_id: str, session_id: str, context: Dict = None) -> Dict:
        workflow_execution_id = str(uuid.uuid4())
        state = AgentState(
            session_id=session_id,
            user_id=user_id,
            message=message,
            original_message=message,
            pseudonymized_message="",
            timestamp=datetime.now(),
            toxicity_score=0.0,
            is_toxic=False,
            compressed_context="",
            intent="",
            target_agent="",
            confidence=0.0,
            rag_results=[],
            agent_response="",
            confidence_score=0.0,
            requires_hitl=False,
            hitl_reason="",
            signatures=[],
            worm_logs=[],
            rgpd_check_passed=True,
            pii_detected=[],
            processing_time=0.0,
            nodes_visited=[],
            user_context=context or {},
            workflow_execution_id=workflow_execution_id,
            hitl_request_id=None,
            governance_risk=None,
            pseudonymized_response=None,
        )
        try:
            result = await self.graph.ainvoke(state)
            print(f"🔍 FINAL - rag_results dans result: {len(result.get('rag_results', []))}")
            return {
                "success": True,
                "session_id": session_id,
                "workflow_execution_id": workflow_execution_id,
                "response": result.get("agent_response", "Je traite votre demande."),
                "agent": result.get("target_agent", "unknown"),
                "confidence": result.get("confidence_score", 0.0),
                "requires_hitl": result.get("requires_hitl", False),
                "hitl_reason": result.get("hitl_reason", ""),
                "hitl_request_id": result.get("hitl_request_id"),
                "rag_results": result.get("rag_results", []),
                "nodes_visited": result.get("nodes_visited", []),
                "pseudonymized_response": result.get("pseudonymized_response"),
                "governance_risk": result.get("governance_risk"),
            }
        except Exception as e:
            print(f"❌ Erreur process_message: {e}")
            self._safe_log_execution(
                session_id=session_id,
                workflow_execution_id=workflow_execution_id,
                event_type=EventType.AGENT_EXECUTION,
                agent_id="workflow",
                execution_status="error",
                error_message=str(e)[:500],
            )
            return {"success": False, "error": str(e), "response": "Une erreur technique est survenue."}
        
    def _kw_match(self, msg: str, keywords: list):
        """Retourne le premier mot-clé qui matche (avec limites de mots), ou None."""
        for kw in keywords:
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, msg, re.IGNORECASE):
                return kw
        return None

    def _kw_in(self, msg: str, keywords: list) -> bool:
        return self._kw_match(msg, keywords) is not None
    # ═════════════════════════════════════════════════════════════════════════
    # NODES INFRASTRUCTURE
    # ═════════════════════════════════════════════════════════════════════════
    async def entry_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("entry")
        state["timestamp"] = datetime.now()

        # 🔥 Pseudonymisation du message entrant
        original_message = state.get("message", "")
        pseudonymized_message = self._pseudonymize_message(original_message)
        state["pseudonymized_message"] = pseudonymized_message
        state["original_message"] = original_message

        print(f"📝 Message original: {original_message[:50]}...")
        print(f"🔒 Message pseudonymisé: {pseudonymized_message[:50]}...")

        # ── Gouvernance: L1 CHAT_REQUEST ────────────────────────────────────
        # Intent/target_agent are not known yet at this point in the graph
        # (router_node sets them) — L2's ROUTING_DECISION event carries
        # those. This event marks that an interaction started at all, with
        # metadata only (message_length, never the raw message).
        self._safe_log_request(
            session_id=state["session_id"],
            workflow_execution_id=state["workflow_execution_id"],
            user_id_pseudo=state.get("user_id"),
            message=original_message,
        )

        return state

    async def moderation_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("moderation")
        pseudo_message = state.get("pseudonymized_message", state["message"])
        toxicity = await self.moderation_agent.check_toxicity(state["message"])
        state["toxicity_score"] = toxicity["score"]
        state["is_toxic"] = toxicity["is_toxic"]
        if toxicity["is_toxic"]:
            state["agent_response"] = "⛔ Votre message contient du contenu inapproprié."

        self._safe_log_execution(
            session_id=state["session_id"],
            workflow_execution_id=state["workflow_execution_id"],
            event_type=EventType.MODERATION_RESULT,
            agent_id="AG01",
            confidence_score=toxicity["score"],
            execution_status="blocked" if toxicity["is_toxic"] else "passed",
        )

        return state

    async def router_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("router")
        msg = state["message"].lower()

        print(f"🔍 Routage du message: {msg[:50]}...")

        CATEGORIES = [
            ("incident", "Incident technique", ["dab", "avalé", "distributeur", "application ne répond", "bug", "panne"], "AG05", 0.88),
            ("closure", "Clôture de compte", ["clôture", "cloture", "fermer mon compte", "résilier", "fermer compte", "livret", "épargne", "PEL", "CEL", "fermer mon livret"], "AG10", 0.95),
            ("succession", "Succession", ["décès", "deces", "succession", "héritage", "héritier", "notaire", "mort"], "AG11", 0.95),
            ("rgpd", "RGPD", ["rgpd", "données personnelles", "suppression données", "droit à l'oubli", "effacement", "portabilité", "opposition profilage", "profilage commercial", "données commerciales", "opposition vente données", "vente de mes données", "données soient vendues"], "AG13", 0.95),
            ("opposition", "Opposition carte", ["opposition", "bloquer ma carte", "carte volée", "carte perdue", "perdu ma carte", "blocage carte", "volé ma carte"], "AG08", 0.95),
            ("fraud", "Fraude", ["fraude", "piratage", "arnaque", "transaction suspecte", "virement non autorisé", "virement frauduleux", "pirate", "piraté", "disparu", "compte vidé"], "AG09", 0.92),
            ("credit", "Crédit", ["credit", "crédit", "pret", "prêt", "emprunt", "immobilier", "financement achat", "financent", "financer", "financement", "voiture", "maison", "appartement", "automobile"], "AG06", 0.90),
            ("complaint", "Réclamation", ["réclamation", "reclamation", "litige", "plainte", "complaint", "je conteste", "contester", "frais indus", "débit incorrect", "erreur de prélèvement", "pas satisfait", "insatisfait", "mécontent", "trop prélevé", "facturé à tort", "montant incorrect", "ce n'est pas normal", "inacceptable", "sans mon autorisation", "sans autorisation"], "AG03", 0.88),
            ("admin", "Administratif", ["rib", "adresse", "changer email", "chéquier", "relevé d'identité", "modifier", "changer"], "AG07", 0.88),
            ("info", "Info générale", ["tarif", "tarifs", "frais", "prix", "coût", "cout", "mdm", "brochure", "conditions tarifaires", "étude", "bancarisation", "research", "carte", "solde"], "AG04", 0.90),
        ]

        for intent, label, keywords, agent, confidence in CATEGORIES:
            matched_kw = self._kw_match(msg, keywords)
            if matched_kw:
                state["intent"] = intent
                state["target_agent"] = agent
                state["confidence"] = confidence
                state["routing_explanation"] = {
                    "intent": intent,
                    "category_label": label,
                    "target_agent": agent,
                    "confidence": confidence,
                    "matched_keyword": matched_kw,
                    "reasoning": f"Le mot-clé « {matched_kw} » a déclenché la catégorie « {label} » → agent {agent}.",
                }
                print(f"   → Routé vers {agent} ({label}) — mot-clé: '{matched_kw}'")
                self._log_routing_decision(state)
                return state

        # Heuristique multi-montants (avant le fallback final)
        amounts_found = re.findall(r'\d[\d\s]{2,}(?:[.,]\d{1,2})?\s*(?:mad|dh|dirham)', msg)
        if len(amounts_found) >= 2:
            state["intent"] = "complaint"
            state["target_agent"] = "AG03"
            state["confidence"] = 0.75
            state["routing_explanation"] = {
                "intent": "complaint",
                "category_label": "Réclamation (heuristique)",
                "target_agent": "AG03",
                "confidence": 0.75,
                "matched_keyword": f"{len(amounts_found)} montants détectés",
                "reasoning": f"Aucun mot-clé explicite, mais {len(amounts_found)} montants distincts détectés dans le message → probable litige.",
            }
            print(f"   → Routé vers AG03 (Réclamation) — heuristique multi-montants ({len(amounts_found)} détectés)")
            self._log_routing_decision(state)
            return state

        # Défaut
        state["intent"] = "info"
        state["target_agent"] = "AG04"
        state["confidence"] = 0.70
        state["routing_explanation"] = {
            "intent": "info",
            "category_label": "Info générale (défaut)",
            "target_agent": "AG04",
            "confidence": 0.70,
            "matched_keyword": None,
            "reasoning": "Aucun mot-clé métier détecté — routage par défaut vers l'agent d'information générale.",
        }
        print(f"   → Routé vers AG04 (Défaut)")

        self._log_routing_decision(state)
        return state
    
    async def rag_retrieve_node(self, state: AgentState) -> AgentState:
        """Récupère les documents pertinents dans ChromaDB"""
        state["nodes_visited"].append("rag_retrieve")

        query = state["message"]
        target_agent = state.get("target_agent", "AG04")

        print(f"📚 RAG: Recherche pour '{query[:50]}...' (agent: {target_agent})")

        results = await self.chroma.similarity_search(
            query,
            k=3,
            agent_filter=target_agent if target_agent != "AG04" else None
        )

        rag_used = bool(results)
        rag_status = "found"

        state["rag_results"] = results

        if results:
            context = self.chroma.format_context(results, max_chars=1000)
            state["compressed_context"] = context
            print(f"   ✅ {len(results)} documents trouvés")
            for r in results:
                print(f"      - {r['metadata'].get('topic', '?')} (score: {r['score']})")
        else:
            state["compressed_context"] = ""
            print(f"   ⚠️ Aucun document trouvé")
            rag_status = "not_found"

            # 🔥 FALLBACK - Correction d'indentation (à l'intérieur du else)
            if "tarif" in query.lower() or "frais" in query.lower():
                state["rag_results"] = [{
                    "content": "Les tarifs bancaires AWB sont disponibles en agence. Tarifs principaux : Compte courant 25 MAD/mois, Carte Visa Classic 120 MAD/an, Virement national 5 MAD.",
                    "metadata": {"topic": "tarifs_fallback", "type": "fallback"},
                    "score": 0.5
                }]
                state["compressed_context"] = "Tarifs bancaires AWB : Compte courant 25 MAD/mois, Carte Visa Classic 120 MAD/an."
                print(f"   📝 Fallback ajouté pour les tarifs")
                rag_status = "fallback"
            elif "carte" in query.lower() or "opposition" in query.lower():
                state["rag_results"] = [{
                    "content": "Opposition carte AWB : Appelez le 0800 00 11 00 (24h/24). Blocage immédiat. Nouvelle carte sous 5-7 jours.",
                    "metadata": {"topic": "opposition_fallback", "type": "fallback"},
                    "score": 0.5
                }]
                state["compressed_context"] = "Opposition carte : 0800 00 11 00, blocage immédiat."
                print(f"   📝 Fallback ajouté pour opposition carte")
                rag_status = "fallback"

        self._safe_log_execution(
            session_id=state["session_id"],
            workflow_execution_id=state["workflow_execution_id"],
            event_type=EventType.RAG_RETRIEVAL,
            agent_id=target_agent,
            rag_used=rag_used,
            rag_documents_count=len(state.get("rag_results", [])),
            execution_status=rag_status,
        )

        return state

    async def hitl_gate_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("hitl_gate")
        requires_hitl = state.get("requires_hitl", False)
        print(f"🚪 hitl_gate_node - requires_hitl: {requires_hitl}")

        if requires_hitl:
            print(f"   Création demande HITL pour {state.get('target_agent')}")
            governance_risk = state.get("governance_risk") or {}
            result = await self.hitl_gate.request_approval(
                state["session_id"],
                state["target_agent"],
                state.get("agent_response", ""),
                state.get("confidence_score", 0.0),
                reason=state.get("hitl_reason") or governance_risk.get("reason"),
                risk_level=governance_risk.get("risk_level"),
                workflow_execution_id=state["workflow_execution_id"],
            )
            print(f"   Résultat: {result}")
            # 🔧 FIX: the real request_id used to be discarded here — the
            # workflow never knew which pending request corresponded to
            # this session, so app.py had no choice but to create a
            # SECOND, disconnected HITL request of its own (see
            # security/hitl_gate.py's docstring for the full story).
            # Threading it into state is what lets app.py stop doing that.
            state["hitl_request_id"] = result.get("request_id")
        else:
            print(f"   Pas de HITL requis")

        return state

    async def output_validator_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("output_validator")
        if len(state.get("agent_response", "")) < 10:
            state["agent_response"] = "Je suis votre assistant AWB. Comment puis-je vous aider ?"
            state["confidence_score"] = 0.5
        return state

    async def end_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("end")

        # Pseudonymisation de la réponse pour l'audit
        response = state.get("agent_response", "")
        if response:
            pseudonymized_response = self._pseudonymize_message(response)
            state["pseudonymized_response"] = pseudonymized_response

        governance_risk = state.get("governance_risk") or {}
        risk_level = governance_risk.get("risk_level")
        outcome = (
            "hitl_pending" if state.get("requires_hitl") else
            ("success" if response else "empty_response")
        )

        # ── Gouvernance: L1 CHAT_RESPONSE (closes out the L1 CHAT_REQUEST
        # opened in entry_node). CHAT_RESPONSE is an L1 event type (see
        # governance.models.TIER_OF_EVENT) — it does NOT also get logged
        # via log_execution()/L2, since that would duplicate this same
        # "the interaction ended" fact under the wrong tier. The L2 trail
        # for this request already exists via the MODERATION_RESULT /
        # ROUTING_DECISION / RAG_RETRIEVAL / AGENT_EXECUTION / JUDGE_EVALUATION
        # events each node logged along the way.
        try:
            risk_obj = None
            if risk_level:
                from governance.models import RiskAssessment, RiskLevel
                risk_obj = RiskAssessment(
                    risk_level=RiskLevel(risk_level),
                    reason=governance_risk.get("reason", ""),
                    hitl_required=governance_risk.get("hitl_required", False),
                    rule_source=governance_risk.get("rule_source", "end_node"),
                )
            self.audit_service.log_response(
                session_id=state["session_id"],
                workflow_execution_id=state["workflow_execution_id"],
                target_agent=state.get("target_agent"),
                confidence=state.get("confidence_score"),
                risk=risk_obj,
                outcome=outcome,
            )
        except Exception as exc:
            print(f"⚠️ Gouvernance (log_response) — action bloquée: {exc}")
            raise

        return state

    def _pseudonymize_message(self, message: str) -> str:
        """
        Pseudonymise un message en remplaçant les informations personnelles.
        """
        import re

        if not message:
            return message

        try:
            # Remplacer les emails
            message = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', message)

            # Remplacer les numéros de téléphone (Maroc)
            message = re.sub(r'(0[5-7][0-9]{8})', '[TELEPHONE]', message)
            message = re.sub(r'(\+212[0-9]{9})', '[TELEPHONE]', message)

            # 🔧 CORRIGÉ : CIN marocain (1-2 lettres + 6-8 chiffres), traité
            # AVANT l'IBAN pour éviter que les regex se marchent dessus.
            message = re.sub(r'\b([A-Z]{1,2}[0-9]{6,8})\b', '[CIN]', message)

            # 🔧 CORRIGÉ : IBAN — minimum 10 caractères alphanumériques après
            # le code pays + clé, pour ne plus capturer les CIN courts par erreur.
            message = re.sub(r'\b([A-Z]{2}[0-9]{2}[A-Z0-9]{10,30})\b', '[IBAN]', message)

            # 🔥 AJOUTÉ : détection heuristique des noms (auto-présentation)
            # "je suis X", "je m'appelle X", "mon nom est X" → [NOM]
            message = re.sub(
                r"(?i:je suis|je m'appelle|mon nom est)\s+([A-ZÀ-Ü][a-zà-ÿ]+(?:\s+[A-ZÀ-Ü][a-zà-ÿ]+){0,2})",
                lambda m: m.group(0).replace(m.group(1), '[NOM]'),
                message
            )

            return message
        except Exception as e:
            print(f"⚠️ Erreur pseudonymisation: {e}")
            return message

    # ═════════════════════════════════════════════════════════════════════════
    # NODES AGENTS MÉTIER
    # ═════════════════════════════════════════════════════════════════════════
    def _build_context(self, state: AgentState) -> Dict:
        return {"chroma": self.chroma, "user_id": state["user_id"]}

    async def credit_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_credit")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 CREDIT_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.credit_agent.process_credit_request(state["message"], state["user_id"], context=context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = response.get("requires_hitl", False)
        self._log_agent_execution(state)
        return state

    async def info_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_info")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])

        print(f"📚 INFO_NODE: {len(rag_results)} documents RAG disponibles")

        # 🔥 Récupérer la session depuis user_context
        user_context = state.get("user_context", {})
        client_session_id = user_context.get("session_id")

        print(f"🔑 Session client dans info_node: {client_session_id}")

        # Construit le contexte pour l'agent
        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        context["session_id"] = client_session_id  # 🔥 Passer la session

        response = await self.info_agent.get_account_info(state["message"], context=context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        self._log_agent_execution(state)
        return state

    async def fraud_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_fraud")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 FRAUD_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.fraud_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = response.get("requires_hitl", False)
        self._log_agent_execution(state)
        return state

    async def complaint_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_complaint")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 COMPLAINT_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.complaint_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = response.get("requires_hitl", False)
        self._log_agent_execution(state)
        return state

    async def incident_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_incident")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 INCIDENT_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results

        response = await self.incident_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = response.get("requires_hitl", False)
        self._log_agent_execution(state)
        return state

    async def admin_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_admin")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 ADMIN_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.admin_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        self._log_agent_execution(state)
        return state

    async def opposition_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_opposition")
        print(f"🔥🔥🔥 OPPOSITION_NODE ATTEINT ! 🔥🔥🔥")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 OPPOSITION_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.opposition_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = response.get("requires_hitl", False)

        print(f"   Réponse envoyée: {response['message'][:100]}...")
        self._log_agent_execution(state)
        return state

    async def closure_node(self, state: AgentState) -> AgentState:
        print("=" * 50)
        print("🔥🔥🔥 CLOSURE_NODE ATTEINT ! 🔥🔥🔥")
        print(f"Message: {state.get('message')}")

        state["nodes_visited"].append("agent_closure")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 CLOSURE_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.closure_agent.process(state["message"], context)

        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = True
        state["hitl_reason"] = response.get("hitl_reason", "")

        print(f"state['requires_hitl']: {state['requires_hitl']}")
        print("=" * 50)
        self._log_agent_execution(state)
        return state

    async def succession_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_succession")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 SUCCESSION_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results
        response = await self.succession_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = True
        self._log_agent_execution(state)
        return state

    async def rgpd_node(self, state: AgentState) -> AgentState:
        state["nodes_visited"].append("agent_rgpd")
        rag_context = state.get("compressed_context", "")
        rag_results = state.get("rag_results", [])
        print(f"📚 RGPD_NODE: {len(rag_results)} documents RAG disponibles")

        context = self._build_context(state)
        context["rag_context"] = rag_context
        context["rag_results"] = rag_results

        response = await self.rgpd_agent.process(state["message"], context)
        state["agent_response"] = response["message"]
        state["confidence_score"] = response["confidence"]
        state["requires_hitl"] = True
        self._log_agent_execution(state)
        return state

    # ═════════════════════════════════════════════════════════════════════════
    # GOUVERNANCE — helpers partagés par tous les nodes ci-dessus
    # ═════════════════════════════════════════════════════════════════════════
    # These wrap governance.audit_service calls with two things every call
    # site needs: (1) never let a governance-layer exception escape into
    # the graph unless AuditService itself decided to fail closed for this
    # risk level (that decision is made INSIDE AuditService._handle_failure,
    # not hidden here — this try/except only stops a raised
    # GovernanceAuditError from propagating past the point the workflow can
    # sensibly handle it), and (2) avoid repeating the same six lines of
    # try/except/logger boilerplate in ten near-identical agent nodes.

    def _safe_log_request(self, **kwargs) -> None:
        try:
            self.audit_service.log_request(**kwargs)
        except Exception as exc:
            print(f"⚠️ Gouvernance (log_request) — action bloquée: {exc}")
            raise

    def _safe_log_execution(self, **kwargs) -> None:
        try:
            self.audit_service.log_execution(**kwargs)
        except Exception as exc:
            print(f"⚠️ Gouvernance (log_execution) — action bloquée: {exc}")
            raise

    def _safe_log_governance(self, **kwargs) -> None:
        try:
            self.audit_service.log_governance(**kwargs)
        except Exception as exc:
            print(f"⚠️ Gouvernance (log_governance) — action bloquée: {exc}")
            raise

    def _log_routing_decision(self, state: AgentState) -> None:
        """Called from router_node's three exit points. Computes the
        centralized risk assessment (governance.risk_policy) ONCE per
        request and stores it on state so every later node (HITL, judge,
        end) reuses the same assessment rather than recomputing it with
        potentially different inputs."""
        risk = self.audit_service.assess_risk(
            intent=state.get("intent"),
            confidence=state.get("confidence"),
        )
        state["governance_risk"] = risk.to_dict()

        self._safe_log_execution(
            session_id=state["session_id"],
            workflow_execution_id=state["workflow_execution_id"],
            event_type=EventType.ROUTING_DECISION,
            agent_id=state.get("target_agent"),
            confidence_score=state.get("confidence"),
            model_info="keyword_router",
            execution_status="routed",
        )

        # A routing decision that is already HIGH/CRITICAL (e.g. the
        # "fraud" intent itself) is a governance-relevant fact on its own,
        # independent of whether the agent later also asks for HITL —
        # record it once here so "intent -> risk -> reason" is traceable
        # even for the (rare) case an agent doesn't end up requesting HITL
        # despite a high-risk intent.
        if risk.risk_level.value in ("HIGH", "CRITICAL"):
            self._safe_log_governance(
                session_id=state["session_id"],
                workflow_execution_id=state["workflow_execution_id"],
                event_type=EventType.POLICY_DECISION,
                risk=risk,
                policy_decision="ESCALATION_CANDIDATE" if risk.hitl_required else "AUTO_ALLOWED_HIGH_RISK",
                governance_action=f"RISK_ASSESSED:{state.get('intent')}",
            )

    def _log_agent_execution(self, state: AgentState) -> None:
        """Called at the end of every agent_* node (credit, info, fraud,
        complaint, incident, admin, opposition, closure, succession,
        rgpd). One shared implementation instead of duplicating the same
        AGENT_EXECUTION logging in all ten nodes."""
        self._safe_log_execution(
            session_id=state["session_id"],
            workflow_execution_id=state["workflow_execution_id"],
            event_type=EventType.AGENT_EXECUTION,
            agent_id=state.get("target_agent"),
            confidence_score=state.get("confidence_score"),
            hitl_triggered=state.get("requires_hitl", False),
            execution_status="success" if state.get("agent_response") else "empty_response",
        )

    # ═════════════════════════════════════════════════════════════════════════
    # ROUTING FUNCTIONS
    # ═════════════════════════════════════════════════════════════════════════
    def route_after_moderation(self, state: AgentState) -> str:
        return "toxic" if state["is_toxic"] else "safe"

    def route_intent(self, state: AgentState) -> str:
        return state.get("intent", "default")

    def route_after_rag(self, state: AgentState) -> str:
        """Redirige vers l'agent cible après le RAG"""
        return state.get("intent", "default")

    def route_hitl(self, state: AgentState) -> str:
        print(f"🔀 ROUTE_HITL - requires_hitl: {state.get('requires_hitl', False)}")
        return "hitl" if state.get("requires_hitl", False) else "direct"

    # ═════════════════════════════════════════════════════════════════════════
    # ⚠️ NODE NON INTÉGRÉ AU GRAPHE — voir note ci-dessous
    # ═════════════════════════════════════════════════════════════════════════
    # Ce node n'est appelé nulle part dans _build_graph() (pas de
    # workflow.add_node("judge", ...)) et référence self.judge_agent, qui
    # n'existe pas dans __init__. Il ne cause plus d'erreur au chargement du
    # module grâce à l'indentation correcte, mais il restera inactif tant que :
    #   1) tu n'ajoutes pas self.judge_agent = ... dans __init__
    #   2) tu n'ajoutes pas workflow.add_node("judge", self.judge_node) et
    #      les edges correspondants dans _build_graph()
    # Ajouter un nœud judge_node
    async def judge_node(self, state: AgentState) -> AgentState:
        """Évalue la qualité de la réponse avant envoi"""
        state["nodes_visited"].append("judge")

        response = state.get("agent_response", "")
        context = state.get("compressed_context", "")

        if not response:
            return state

        judge_system = (
            "Tu es un évaluateur qualité indépendant pour une banque. "
            "Évalue objectivement, sans complaisance. Réponds UNIQUEMENT en JSON, sans texte autour."
        )

        judge_prompt = f"""Contexte RAG disponible : {context[:1000] if context else "(aucun)"}

Réponse de l'agent à évaluer : {response[:1000]}

Note chaque critère de 0 à 10 :
1. factualite : fidélité au contexte RAG
2. coherence : respect des règles métier bancaires
3. absence_hallucination : absence de montants/dates/références inventés
Ne pénalise jamais une réponse simplement parce qu'elle ne cite pas de documents RAG quand la question ne l'exigeait pas (salutation, question générale, remerciement).
Format JSON strict : {{"factualite": X, "coherence": Y, "absence_hallucination": Z, "score_total": moyenne, "decision": "ACCEPT ou REJECT"}}"""

        try:
            judge_response = await self.judge_agent.call_llm(
                judge_prompt,
                system=judge_system,
                max_tokens=200,
                temperature=0.1,
            )
            import json, re
            json_match = re.search(r'\{.*\}', judge_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                score = result.get("score_total", 10)
                state["judge_evaluation"] = result
                print(f"⚖️ JUDGE - score: {score}, decision: {result.get('decision')}")

                if score < 6:
                    state["agent_response"] = "Je dois vérifier cette information avant de vous répondre. Un conseiller vous contactera sous peu."
                    state["requires_hitl"] = True
                    state["hitl_reason"] = f"Score Judge insuffisant: {score}/10"

                # ── Gouvernance: L2 JUDGE_EVALUATION toujours, + L3
                # JUDGE_ESCALATION si le score a déclenché une escalade.
                # NOTE, bug pré-existant distinct de ce fichier de
                # gouvernance: dans _build_graph, hitl_gate_node s'exécute
                # AVANT judge_node (agent -> hitl_gate -> output_validator
                # -> judge -> end). Donc positionner requires_hitl=True ici
                # ne fait PAS créer de nouvelle demande HITL via
                # self.hitl_gate (ce node ne s'exécute plus après judge) —
                # seuls agent_response/hitl_reason renvoyés à l'appelant
                # reflètent l'escalade. L'événement L3 ci-dessous enregistre
                # fidèlement "le judge a déclenché une escalade" même si le
                # gate HITL lui-même n'a pas été re-sollicité ; si vous
                # voulez que le score du judge bloque réellement la
                # réponse via HITL, il faut réordonner les edges du graphe
                # (judge avant hitl_gate) — décision métier volontairement
                # laissée hors de cette couche de gouvernance.
                self._safe_log_execution(
                    session_id=state["session_id"],
                    workflow_execution_id=state["workflow_execution_id"],
                    event_type=EventType.JUDGE_EVALUATION,
                    agent_id=state.get("target_agent"),
                    judge_score=score,
                    execution_status=result.get("decision", "").lower() or None,
                )

                if score < 6:
                    self._safe_log_governance(
                        session_id=state["session_id"],
                        workflow_execution_id=state["workflow_execution_id"],
                        event_type=EventType.JUDGE_ESCALATION,
                        escalation_reason=f"Judge score {score}/10 below threshold",
                        hitl_request_id=state.get("hitl_request_id"),
                        judge_result=result,
                        policy_decision="ESCALATED",
                        governance_action="JUDGE_SCORE_ESCALATION",
                    )
        except Exception as e:
            print(f"⚠️ Erreur Judge: {e}")

        return state
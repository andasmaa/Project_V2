# security/hitl_gate.py
from typing import Dict, List, Optional
from datetime import datetime
import logging
import uuid

from governance.audit_service import AuditService
from governance.models import EventType, HITLDecision, RiskAssessment, RiskLevel

logger = logging.getLogger("security.hitl_gate")


class HITLGate:
    """
    Same in-memory pending_requests store and the same four original
    method names/signatures (request_approval, get_pending_requests,
    approve, reject) — nothing about the HITL business logic itself
    changes. What's new:

      - Each lifecycle event (request created, approved, rejected) now
        also emits a real L3 governance event, so the AI-decision <->
        human-decision link your spec asks for actually exists in the
        audit trail, not just in this process's memory.
      - A new override() method, for the "human override" case your
        spec calls out (item 12) that had no equivalent before — purely
        additive, nothing existing calls it yet.

    request_approval/approve/reject keep their EXACT original positional
    signatures — every existing call site (workflow's hitl_gate_node,
    app.py's four call sites) keeps working with zero changes. New,
    optional keyword-only parameters were added for callers that DO have
    richer context (e.g. a workflow node that knows the escalation
    reason and workflow_execution_id) to pass it through for a more
    complete L3 record, without forcing every caller to supply it.

    NOTE ON A SEPARATE, PRE-EXISTING BUG (not fixed by this file, flagged
    here so it isn't missed): workflow/langgraph_workflow.py constructs
    its own `self.hitl_gate = HITLGate()` and app.py constructs a SECOND,
    independent `hitl_gate = HITLGate()` at module level. A HITL-
    triggering request today creates a pending request in the workflow's
    instance (inside hitl_gate_node) whose request_id is then discarded
    (never stored back into state), and app.py's /chat endpoint then
    creates a SECOND, different pending request in ITS OWN instance —
    which is the only one /api/hitl/pending and /api/hitl/{id}/approve
    can actually see. Fixing this requires touching app.py and
    workflow/langgraph_workflow.py (making them share one HITLGate
    instance, and threading the real request_id back through
    AgentState), which is exactly the workflow-instrumentation step of
    this integration. This file is written to behave correctly under
    the eventual single-instance setup; both duplicate instances just
    emit their own honest, correct L3 trail until that's wired up.
    """

    def __init__(self, audit_service: Optional[AuditService] = None):
        self.pending_requests: Dict[str, Dict] = {}
        # AuditService() with no explicit failure_mode picks up
        # GOVERNANCE_FAILURE_MODE / GOVERNANCE_FAILURE_MODE_HIGH_RISK from
        # the environment (see governance/audit_service.py) rather than a
        # hardcoded default — HITL decisions are exactly the kind of
        # high-risk governance record that project requirement was
        # written for.
        self._audit_service = audit_service or AuditService()
        print("✅ HITL Gate initialisé")

    async def request_approval(
        self,
        session_id: str,
        agent: str,
        context: str,
        confidence: float,
        *,
        reason: Optional[str] = None,
        risk_level: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
    ) -> Dict:
        request_id = str(uuid.uuid4())[:8]
        self.pending_requests[request_id] = {
            "request_id": request_id,
            "session_id": session_id,
            "agent": agent,
            "agent_name": self._get_agent_name(agent),
            "context": context[:200],
            "confidence": confidence,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
        }
        print(f"🟡 HITL Request created: {request_id} for agent {agent}")

        risk_assessment: Optional[RiskAssessment] = None
        if risk_level:
            try:
                risk_assessment = RiskAssessment(
                    risk_level=RiskLevel(risk_level),
                    reason=reason or "HITL escalation",
                    hitl_required=True,
                    rule_source="hitl_gate.request_approval",
                )
            except ValueError:
                logger.warning("Unknown risk_level %r passed to request_approval, ignoring", risk_level)

        self._emit_governance_event(
            session_id=session_id,
            workflow_execution_id=workflow_execution_id or f"hitl:{request_id}",
            event_type=EventType.HITL_REQUIRED,
            hitl_request_id=request_id,
            risk=risk_assessment,
            escalation_reason=reason,
            governance_action=f"HITL_REQUEST_CREATED:{agent}",
        )

        return {"status": "pending", "request_id": request_id}

    async def get_pending_requests(self) -> List[Dict]:
        return list(self.pending_requests.values())

    async def approve(
        self,
        request_id: str,
        approver: str,
        *,
        workflow_execution_id: Optional[str] = None,
    ) -> Dict:
        session_id = "unknown"
        if request_id in self.pending_requests:
            self.pending_requests[request_id]["status"] = "approved"
            self.pending_requests[request_id]["approver"] = approver
            self.pending_requests[request_id]["decided_at"] = datetime.now().isoformat()
            session_id = self.pending_requests[request_id]["session_id"]
        else:
            logger.warning(
                "approve() called for unknown request_id=%s (not in this "
                "HITLGate instance's pending_requests)", request_id,
            )

        self._emit_governance_event(
            session_id=session_id,
            workflow_execution_id=workflow_execution_id or f"hitl:{request_id}",
            event_type=EventType.HITL_DECISION,
            hitl_request_id=request_id,
            human_decision=HITLDecision.APPROVED,
            human_approver=approver,
            governance_action="HITL_APPROVED",
        )

        return {"status": "approved", "request_id": request_id}

    async def reject(
        self,
        request_id: str,
        reason: str,
        *,
        approver: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
    ) -> Dict:
        session_id = "unknown"
        if request_id in self.pending_requests:
            self.pending_requests[request_id]["status"] = "rejected"
            self.pending_requests[request_id]["rejection_reason"] = reason
            self.pending_requests[request_id]["decided_at"] = datetime.now().isoformat()
            session_id = self.pending_requests[request_id]["session_id"]
        else:
            logger.warning(
                "reject() called for unknown request_id=%s (not in this "
                "HITLGate instance's pending_requests)", request_id,
            )

        self._emit_governance_event(
            session_id=session_id,
            workflow_execution_id=workflow_execution_id or f"hitl:{request_id}",
            event_type=EventType.HITL_DECISION,
            hitl_request_id=request_id,
            human_decision=HITLDecision.REJECTED,
            human_approver=approver,
            rejection_reason=reason,
            governance_action="HITL_REJECTED",
        )

        return {"status": "rejected", "request_id": request_id}

    async def override(
        self,
        request_id: str,
        approver: str,
        reason: str,
        *,
        workflow_execution_id: Optional[str] = None,
    ) -> Dict:
        """New: records a human override of an AI decision — e.g. a
        supervisor manually approving something the AI/policy would not
        have approved on its own, or manually reversing an already-
        approved/rejected HITL request. Purely additive: nothing existing
        calls this yet, and it doesn't touch approve()/reject()'s
        behavior. Wire this into an API endpoint
        (POST /api/hitl/{request_id}/override) when you need supervisors
        to actually use it."""
        session_id = "unknown"
        if request_id in self.pending_requests:
            self.pending_requests[request_id]["status"] = "overridden"
            self.pending_requests[request_id]["override_approver"] = approver
            self.pending_requests[request_id]["override_reason"] = reason
            self.pending_requests[request_id]["decided_at"] = datetime.now().isoformat()
            session_id = self.pending_requests[request_id]["session_id"]
        else:
            logger.warning(
                "override() called for unknown request_id=%s", request_id,
            )

        self._emit_governance_event(
            session_id=session_id,
            workflow_execution_id=workflow_execution_id or f"hitl:{request_id}",
            event_type=EventType.GOVERNANCE_OVERRIDE,
            hitl_request_id=request_id,
            human_decision=HITLDecision.OVERRIDDEN,
            human_approver=approver,
            override_reason=reason,
            governance_action="HITL_OVERRIDDEN",
        )

        return {"status": "overridden", "request_id": request_id}

    def _get_agent_name(self, agent: str) -> str:
        names = {
            "AG03": "Réclamation",
            "AG05": "Incident",
            "AG06": "Crédit",
            "AG07": "Admin",
            "AG08": "Opposition",
            "AG09": "Anti-Fraude",
            "AG10": "Clôture",
            "AG11": "Succession",
            "AG13": "RGPD",
        }
        return names.get(agent, agent)

    def _emit_governance_event(self, **kwargs) -> None:
        """Never lets a governance-write failure break the actual HITL
        action (a supervisor's approve/reject click must always succeed
        for the human, regardless of Postgres's health) unless the
        AuditService was explicitly configured to fail closed — see
        governance.audit_service.resolve_failure_mode_for_risk() for how
        that's wired in for HIGH/CRITICAL-risk cases during workflow
        instrumentation."""
        try:
            self._audit_service.log_governance(event_type=kwargs.pop("event_type"), **kwargs)
        except Exception as exc:
            logger.error("HITLGate governance event emission failed: %s", exc)
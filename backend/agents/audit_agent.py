from agents.base_agent import BaseAgent
from typing import Dict, Optional
import logging

from governance.audit_service import AuditService
from governance.models import EventType, GovernanceFailureMode

logger = logging.getLogger("agents.audit_agent")


class AuditAgent(BaseAgent):
    """
    Historically this agent kept its own in-memory list of "worm_logs"
    that nothing else ever read (log_action() had no other caller in the
    codebase, and the list was lost on every process restart). That made
    it a second, disconnected audit store in name only.

    It now delegates every log_action() call to the governance audit
    service, so there is ONE source of truth for audit persistence
    (governance.audit_service -> governance.audit_logger -> Postgres,
    hash-chained) rather than this agent silently accumulating logs
    nobody could read back.

    BaseAgent's interface (agent_id, model, process()) is preserved
    exactly, including process()'s original return shape, since app.py's
    GET /api/agents metadata endpoint and any future LangGraph routing
    to "AG14" depend on this class remaining a valid, drop-in agent.
    """

    def __init__(self, audit_service: Optional[AuditService] = None):
        super().__init__("AG14", "qwen:7b")
        # Same fail-open reasoning as security/worm_audit.py's wrapper:
        # a governance write failure here must not take down whichever
        # agent/flow called log_action() as a side effect.
        self._audit_service = audit_service or AuditService(
            failure_mode=GovernanceFailureMode.FAIL_OPEN
        )

    async def log_action(self, action: str, entity_id: str, details: Dict) -> Dict:
        """Preserves the original signature and return shape exactly, so
        any existing or future caller of `audit_agent.log_action(...)`
        keeps working unchanged. Internally, records a real L3 governance
        event instead of appending to a list nothing reads.

        HONEST LIMITATION, stated explicitly rather than hidden: this
        method's signature (action, entity_id, details) predates the
        governance schema and carries no session_id/workflow_execution_id,
        so — exactly like security/worm_audit.py's legacy write() bridge —
        the resulting L3 row cannot be linked into a specific request's
        full L1/L2/L3 chain-of-custody. `entity_id` is used as the best
        available correlation key. For a request-scoped, fully
        correlated governance trail, call
        governance.audit_service.AuditService.log_governance(...)
        directly from the workflow node that has the real session_id and
        workflow_execution_id (this is what
        workflow/langgraph_workflow.py's HITL/judge nodes do).
        """
        log_entry = {
            "timestamp": _now_iso(),
            "action": action,
            "entity_id": entity_id,
            "details": details,
            "agent_id": self.agent_id,
        }

        try:
            self._audit_service.log_governance(
                session_id=str(entity_id or "audit_agent_unknown"),
                workflow_execution_id=f"audit_agent:{action}",
                event_type=EventType.POLICY_DECISION,
                governance_action=action,
                policy_decision=str(details.get("policy_decision")) if isinstance(details, dict) and details.get("policy_decision") else None,
            )
        except Exception as exc:
            # Never let a governance-layer failure break the caller of
            # log_action() — logged loudly, not swallowed silently.
            logger.error("AuditAgent.log_action governance write failed: %s", exc)

        return log_entry

    async def process(self, message: str, context: Dict = None) -> Dict:
        return {"message": "Action auditée", "confidence": 1.0}


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat()
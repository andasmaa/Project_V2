"""
governance/audit_service.py

High-level governance façade.

The LangGraph workflow should interact with this service rather than
directly constructing SQL queries.

This keeps governance logic separate from business/agent logic.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from governance.audit_logger import AuditLogger
from governance.models import (
    EventType,
    GovernanceFailureMode,
    L1InteractionEvent,
    L2ExecutionEvent,
    L3GovernanceEvent,
    RiskAssessment,
)
from governance.pii_protection import detect_pii
from governance.risk_policy import assess_request


logger = logging.getLogger("governance.audit_service")


class GovernanceAuditError(RuntimeError):
    """
    Raised when a governance operation fails.
    """


def _env_failure_mode(var_name: str, default: GovernanceFailureMode) -> GovernanceFailureMode:
    """Reads a GovernanceFailureMode from an environment variable
    ('fail_open' | 'fail_closed'), falling back to `default` for any
    unset/unrecognized value. Centralizing this here means
    GOVERNANCE_FAILURE_MODE (set in .env) is actually honored, instead of
    every caller needing to remember to read it themselves."""
    raw = os.getenv(var_name, "").strip().lower()
    if raw == GovernanceFailureMode.FAIL_CLOSED.value:
        return GovernanceFailureMode.FAIL_CLOSED
    if raw == GovernanceFailureMode.FAIL_OPEN.value:
        return GovernanceFailureMode.FAIL_OPEN
    return default


#: The failure mode used by AuditService when the caller doesn't pass one
#: explicitly. Resolved once at import time from GOVERNANCE_FAILURE_MODE.
DEFAULT_FAILURE_MODE = _env_failure_mode("GOVERNANCE_FAILURE_MODE", GovernanceFailureMode.FAIL_OPEN)

#: A stricter default specifically for HIGH/CRITICAL-risk operations, read
#: from GOVERNANCE_FAILURE_MODE_HIGH_RISK. Callers that know the risk
#: level of the operation they're logging (the workflow's governance
#: instrumentation does) can pass this in instead of the blanket default —
#: see resolve_failure_mode_for_risk() below.
HIGH_RISK_FAILURE_MODE = _env_failure_mode("GOVERNANCE_FAILURE_MODE_HIGH_RISK", DEFAULT_FAILURE_MODE)


def resolve_failure_mode_for_risk(risk_level: Optional[str]) -> GovernanceFailureMode:
    """HIGH/CRITICAL risk operations use GOVERNANCE_FAILURE_MODE_HIGH_RISK
    (defaults to fail_closed in the shipped .env.governance.example);
    everything else uses the blanket GOVERNANCE_FAILURE_MODE. This is
    what makes 'fail-open vs fail-closed should be configurable, not
    hardcoded' (project requirement) actually true per-call, not just
    per-process."""
    if risk_level in ("HIGH", "CRITICAL"):
        return HIGH_RISK_FAILURE_MODE
    return DEFAULT_FAILURE_MODE


class AuditService:

    def __init__(
        self,
        logger_backend: Optional[AuditLogger] = None,
        failure_mode: Optional[GovernanceFailureMode] = None,
    ):
        self.logger_backend = logger_backend or AuditLogger()
        # None (the default) now means "use the env-configured default",
        # not a hardcoded FAIL_OPEN — callers that need a specific,
        # non-negotiable mode (e.g. the worm_audit.py/audit_agent.py
        # compatibility shims, which must always fail open) still pass
        # it explicitly and get exactly that.
        self.failure_mode = failure_mode if failure_mode is not None else DEFAULT_FAILURE_MODE

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def _handle_failure(
        self,
        operation: str,
        exc: Exception,
        failure_mode: Optional[GovernanceFailureMode] = None,
    ) -> None:

        logger.exception(
            "Governance audit operation failed: %s",
            operation,
        )

        effective_mode = failure_mode if failure_mode is not None else self.failure_mode
        if effective_mode == GovernanceFailureMode.FAIL_CLOSED:
            raise GovernanceAuditError(
                f"Governance operation failed: {operation}"
            ) from exc

    # ------------------------------------------------------------------
    # Risk
    # ------------------------------------------------------------------

    def assess_risk(
        self,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        judge_score: Optional[float] = None,
    ) -> RiskAssessment:

        return assess_request(
            intent=intent,
            confidence=confidence,
            judge_score=judge_score,
        )

    # ------------------------------------------------------------------
    # L1
    # ------------------------------------------------------------------

    def log_request(
        self,
        session_id: str,
        workflow_execution_id: str,
        user_id_pseudo: Optional[str],
        message: str,
        intent: Optional[str] = None,
        target_agent: Optional[str] = None,
        risk: Optional[RiskAssessment] = None,
        failure_mode: Optional[GovernanceFailureMode] = None,
    ) -> Optional[str]:

        try:
            pii = detect_pii(message or "")

            event = L1InteractionEvent(
                session_id=session_id,
                workflow_execution_id=workflow_execution_id,
                event_type=EventType.CHAT_REQUEST,
                user_id_pseudo=user_id_pseudo,
                request_type="chat_message",
                message_length=len(message or ""),
                detected_intent=intent,
                target_agent=target_agent,
                pii=pii,
                risk_level=risk.risk_level if risk else None,
                outcome=None,
            )

            return self.logger_backend.write_l1(event)

        except Exception as exc:
            self._handle_failure(
                "log_request", exc,
                failure_mode=failure_mode or (
                    resolve_failure_mode_for_risk(risk.risk_level.value) if risk else None
                ),
            )
            return None

    def log_response(
        self,
        session_id: str,
        workflow_execution_id: str,
        target_agent: Optional[str],
        confidence: Optional[float],
        risk: Optional[RiskAssessment],
        outcome: str = "success",
        failure_mode: Optional[GovernanceFailureMode] = None,
    ) -> Optional[str]:

        try:
            event = L1InteractionEvent(
                session_id=session_id,
                workflow_execution_id=workflow_execution_id,
                event_type=EventType.CHAT_RESPONSE,
                target_agent=target_agent,
                risk_level=risk.risk_level if risk else None,
                outcome=outcome,
            )

            return self.logger_backend.write_l1(event)

        except Exception as exc:
            self._handle_failure(
                "log_response", exc,
                failure_mode=failure_mode or (
                    resolve_failure_mode_for_risk(risk.risk_level.value) if risk else None
                ),
            )
            return None

    # ------------------------------------------------------------------
    # L2
    # ------------------------------------------------------------------

    def log_execution(
        self,
        session_id: str,
        workflow_execution_id: str,
        event_type: EventType,
        agent_id: Optional[str] = None,
        nodes_visited: Optional[list[str]] = None,
        rag_used: Optional[bool] = None,
        rag_documents_count: Optional[int] = None,
        confidence_score: Optional[float] = None,
        processing_duration_ms: Optional[int] = None,
        model_info: Optional[str] = None,
        judge_score: Optional[float] = None,
        hitl_triggered: Optional[bool] = None,
        execution_status: Optional[str] = None,
        error_message: Optional[str] = None,
        failure_mode: Optional[GovernanceFailureMode] = None,
    ) -> Optional[str]:

        try:
            event = L2ExecutionEvent(
                session_id=session_id,
                workflow_execution_id=workflow_execution_id,
                event_type=event_type,
                agent_id=agent_id,
                nodes_visited=nodes_visited or [],
                rag_used=rag_used,
                rag_documents_count=rag_documents_count,
                confidence_score=confidence_score,
                processing_duration_ms=processing_duration_ms,
                model_info=model_info,
                judge_score=judge_score,
                hitl_triggered=hitl_triggered,
                execution_status=execution_status,
                error_message=(
                    error_message[:1000]
                    if error_message
                    else None
                ),
            )

            return self.logger_backend.write_l2(event)

        except Exception as exc:
            self._handle_failure(
                f"log_execution:{event_type.value}",
                exc,
                failure_mode=failure_mode,
            )
            return None

    # ------------------------------------------------------------------
    # L3
    # ------------------------------------------------------------------

    def log_governance(
        self,
        session_id: str,
        workflow_execution_id: str,
        event_type: EventType,
        risk: Optional[RiskAssessment] = None,
        escalation_reason: Optional[str] = None,
        hitl_request_id: Optional[str] = None,
        human_decision: Optional[Any] = None,
        human_approver: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        override_reason: Optional[str] = None,
        judge_result: Optional[Dict[str, Any]] = None,
        policy_decision: Optional[str] = None,
        governance_action: Optional[str] = None,
        failure_mode: Optional[GovernanceFailureMode] = None,
    ) -> Optional[str]:

        try:
            event = L3GovernanceEvent(
                session_id=session_id,
                workflow_execution_id=workflow_execution_id,
                event_type=event_type,
                risk_level=(
                    risk.risk_level
                    if risk
                    else None
                ),
                escalation_reason=escalation_reason
                or (risk.reason if risk else None),
                hitl_required=(
                    risk.hitl_required
                    if risk
                    else None
                ),
                hitl_request_id=hitl_request_id,
                human_decision=human_decision,
                human_approver=human_approver,
                rejection_reason=rejection_reason,
                override_reason=override_reason,
                judge_result=judge_result,
                policy_decision=policy_decision,
                governance_action=governance_action,
            )

            return self.logger_backend.write_l3(event)

        except Exception as exc:
            self._handle_failure(
                f"log_governance:{event_type.value}",
                exc,
                failure_mode=failure_mode or (
                    resolve_failure_mode_for_risk(risk.risk_level.value) if risk else None
                ),
            )
            return None
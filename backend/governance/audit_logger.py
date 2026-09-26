"""
governance/audit_logger.py

Low-level PostgreSQL audit writers.

This module knows:

- how L1/L2/L3 events map to database columns;
- how to retrieve the latest hash;
- how to calculate the next hash;
- how to insert an immutable audit row.

Higher-level workflow logic belongs in audit_service.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from governance.audit_schema import (
    TABLE_NAMES,
    GovernanceDBConfig,
    connection_scope,
)
from governance.integrity import compute_entry_hash, normalize_timestamp, GENESIS_HASH
from governance.models import (
    L1InteractionEvent,
    L2ExecutionEvent,
    L3GovernanceEvent,
    Tier,
)

logger = logging.getLogger("governance.audit_logger")


class AuditLogger:
    """
    PostgreSQL audit writer.

    One AuditLogger instance can be shared by the application.
    """

    def __init__(
        self,
        config: Optional[GovernanceDBConfig] = None,
    ):
        self.config = config

    # ------------------------------------------------------------------
    # Hash handling
    # ------------------------------------------------------------------

    def _get_previous_hash(
        self,
        cur,
        table_name: str,
    ) -> str:
        """
        Get the latest hash for a tier.

        The database primary key defines insertion order.
        """

        cur.execute(
            f"""
            SELECT entry_hash
            FROM {table_name}
            ORDER BY id DESC
            LIMIT 1
            """
        )

        row = cur.fetchone()

        if not row:
            return GENESIS_HASH

        return row[0]

    # ------------------------------------------------------------------
    # L1
    # ------------------------------------------------------------------

    def write_l1(
        self,
        event: L1InteractionEvent,
    ) -> str:

        table = TABLE_NAMES[Tier.L1]

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                previous_hash = self._get_previous_hash(
                    cur,
                    table,
                )

                pii = event.pii.to_dict() if event.pii else {}

                # IMPORTANT: this flat shape must match, key-for-key, what
                # integrity.normalize_db_row() reconstructs from the DB row
                # at verification time (flat pii_detected / pii_entity_types
                # columns) — NOT event.to_dict()'s nested {"pii": {...}}
                # shape. Hashing event.to_dict() here previously caused
                # verify_rows() to report every single row as tampered,
                # even completely untouched ones, because the write-time
                # and verify-time payloads were structurally different
                # dicts (confirmed by live testing).
                event_data = {
                    "event_id": event.event_id,
                    "session_id": event.session_id,
                    "workflow_execution_id": event.workflow_execution_id,
                    "event_type": event.event_type.value,
                    "user_id_pseudo": event.user_id_pseudo,
                    "request_type": event.request_type,
                    "message_length": event.message_length,
                    "detected_intent": event.detected_intent,
                    "target_agent": event.target_agent,
                    "pii_detected": pii.get("pii_detected", False),
                    "pii_entity_types": sorted(pii.get("entity_types") or []),
                    "risk_level": event.risk_level.value if event.risk_level else None,
                    "outcome": event.outcome,
                    "created_at": normalize_timestamp(event.created_at),
                }

                entry_hash = compute_entry_hash(
                    event_data,
                    previous_hash,
                )

                cur.execute(
                    f"""
                    INSERT INTO {table} (
                        event_id,
                        prev_hash,
                        entry_hash,
                        session_id,
                        workflow_execution_id,
                        event_type,
                        user_id_pseudo,
                        request_type,
                        message_length,
                        detected_intent,
                        target_agent,
                        pii_detected,
                        pii_entity_types,
                        risk_level,
                        outcome,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        event.event_id,
                        previous_hash,
                        entry_hash,
                        event.session_id,
                        event.workflow_execution_id,
                        event.event_type.value,
                        event.user_id_pseudo,
                        event.request_type,
                        event.message_length,
                        event.detected_intent,
                        event.target_agent,
                        pii.get("pii_detected", False),
                        pii.get("entity_types", []),
                        event.risk_level.value
                        if event.risk_level
                        else None,
                        event.outcome,
                        event.created_at,
                    ),
                )

        return event.event_id

    # ------------------------------------------------------------------
    # L2
    # ------------------------------------------------------------------

    def write_l2(
        self,
        event: L2ExecutionEvent,
    ) -> str:

        table = TABLE_NAMES[Tier.L2]

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                previous_hash = self._get_previous_hash(
                    cur,
                    table,
                )

                # Same principle as write_l1: flat shape matching the DB
                # columns exactly, not event.to_dict()'s dataclass shape.
                event_data = {
                    "event_id": event.event_id,
                    "session_id": event.session_id,
                    "workflow_execution_id": event.workflow_execution_id,
                    "event_type": event.event_type.value,
                    "agent_id": event.agent_id,
                    "nodes_visited": list(event.nodes_visited or []),
                    "rag_used": event.rag_used,
                    "rag_documents_count": event.rag_documents_count,
                    "confidence_score": float(event.confidence_score) if event.confidence_score is not None else None,
                    "processing_duration_ms": event.processing_duration_ms,
                    "model_info": event.model_info,
                    "judge_score": float(event.judge_score) if event.judge_score is not None else None,
                    "hitl_triggered": event.hitl_triggered,
                    "execution_status": event.execution_status,
                    "error_message": event.error_message,
                    "created_at": normalize_timestamp(event.created_at),
                }

                entry_hash = compute_entry_hash(
                    event_data,
                    previous_hash,
                )

                cur.execute(
                    f"""
                    INSERT INTO {table} (
                        event_id,
                        prev_hash,
                        entry_hash,
                        session_id,
                        workflow_execution_id,
                        event_type,
                        agent_id,
                        nodes_visited,
                        rag_used,
                        rag_documents_count,
                        confidence_score,
                        processing_duration_ms,
                        model_info,
                        judge_score,
                        hitl_triggered,
                        execution_status,
                        error_message,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    """,
                    (
                        event.event_id,
                        previous_hash,
                        entry_hash,
                        event.session_id,
                        event.workflow_execution_id,
                        event.event_type.value,
                        event.agent_id,
                        event.nodes_visited,
                        event.rag_used,
                        event.rag_documents_count,
                        event.confidence_score,
                        event.processing_duration_ms,
                        event.model_info,
                        event.judge_score,
                        event.hitl_triggered,
                        event.execution_status,
                        event.error_message,
                        event.created_at,
                    ),
                )

        return event.event_id

    # ------------------------------------------------------------------
    # L3
    # ------------------------------------------------------------------

    def write_l3(
        self,
        event: L3GovernanceEvent,
    ) -> str:

        table = TABLE_NAMES[Tier.L3]

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                previous_hash = self._get_previous_hash(
                    cur,
                    table,
                )

                # Same principle as write_l1/write_l2: flat shape matching
                # the DB columns exactly.
                event_data = {
                    "event_id": event.event_id,
                    "session_id": event.session_id,
                    "workflow_execution_id": event.workflow_execution_id,
                    "event_type": event.event_type.value,
                    "risk_level": event.risk_level.value if event.risk_level else None,
                    "escalation_reason": event.escalation_reason,
                    "hitl_required": event.hitl_required,
                    "hitl_request_id": event.hitl_request_id,
                    "human_decision": event.human_decision.value if event.human_decision else None,
                    "human_approver": event.human_approver,
                    "rejection_reason": event.rejection_reason,
                    "override_reason": event.override_reason,
                    "judge_result": event.judge_result if event.judge_result else None,
                    "policy_decision": event.policy_decision,
                    "governance_action": event.governance_action,
                    "created_at": normalize_timestamp(event.created_at),
                }

                entry_hash = compute_entry_hash(
                    event_data,
                    previous_hash,
                )

                judge_result = (
                    json.dumps(event.judge_result)
                    if event.judge_result is not None
                    else None
                )

                cur.execute(
                    f"""
                    INSERT INTO {table} (
                        event_id,
                        prev_hash,
                        entry_hash,
                        session_id,
                        workflow_execution_id,
                        event_type,
                        risk_level,
                        escalation_reason,
                        hitl_required,
                        hitl_request_id,
                        human_decision,
                        human_approver,
                        rejection_reason,
                        override_reason,
                        judge_result,
                        policy_decision,
                        governance_action,
                        created_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s
                    )
                    """,
                    (
                        event.event_id,
                        previous_hash,
                        entry_hash,
                        event.session_id,
                        event.workflow_execution_id,
                        event.event_type.value,
                        event.risk_level.value
                        if event.risk_level
                        else None,
                        event.escalation_reason,
                        event.hitl_required,
                        event.hitl_request_id,
                        event.human_decision.value
                        if event.human_decision
                        else None,
                        event.human_approver,
                        event.rejection_reason,
                        event.override_reason,
                        judge_result,
                        event.policy_decision,
                        event.governance_action,
                        event.created_at,
                    ),
                )

        return event.event_id
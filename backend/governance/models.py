"""
governance/models.py
=====================
Shared, framework-agnostic types for the governance/audit layer.

Every other governance module (audit_logger, audit_service, risk_policy,
integrity, metrics) imports from here so that event shapes, table/column
names and vocabulary (risk levels, event types...) are defined exactly
once. This is what makes the "table name mismatch" class of bug (the one
found between the original schema.sql and verify_chain.py) structurally
impossible going forward: nothing downstream invents its own field names.

Nothing in this file talks to Postgres, LangGraph, or FastAPI — it is pure
data definitions so it can be imported from anywhere (workflow nodes,
tests, the Streamlit dashboard, the Banking77 evaluation script) without
pulling in heavy dependencies.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════

class Tier(str, Enum):
    """The three audit tiers. Values match the table-name suffix used in
    governance/audit_schema.py (audit_l1_interaction, audit_l2_execution,
    audit_l3_governance) — keep these in sync if you ever rename a table."""
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class RiskLevel(str, Enum):
    """Ordered from least to most severe. `severity_rank` gives a total
    order so risk_policy.py can do `max(risk_a, risk_b, key=severity_rank)`
    style comparisons without string hacks."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

    @property
    def severity_rank(self) -> int:
        return {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }[self]

    @staticmethod
    def max(*levels: "RiskLevel") -> "RiskLevel":
        """Returns the most severe of the given risk levels. Used when a
        single request accumulates risk from several independent signals
        (e.g. a HIGH-risk intent AND a low-confidence response)."""
        return max(levels, key=lambda lvl: lvl.severity_rank)


class EventType(str, Enum):
    """Every audit event the governance layer knows how to record, grouped
    by which tier it normally belongs to (see TIER_OF_EVENT below). This is
    intentionally a flat enum rather than three separate ones: a few event
    types genuinely appear at more than one tier depending on context (e.g.
    JUDGE_EVALUATION is L2 when the judge accepts, L3 when it escalates),
    and callers should not have to pick the "right" enum class for that.

    Corresponds to the workflow lifecycle in the project brief:
    REQUEST -> MODERATION -> ROUTER -> RAG -> AGENT -> HITL(?) -> JUDGE -> RESPONSE
    """
    # L1 — interaction
    CHAT_REQUEST = "CHAT_REQUEST"
    CHAT_RESPONSE = "CHAT_RESPONSE"

    # L2 — execution
    MODERATION_RESULT = "MODERATION_RESULT"
    ROUTING_DECISION = "ROUTING_DECISION"
    RAG_RETRIEVAL = "RAG_RETRIEVAL"
    AGENT_EXECUTION = "AGENT_EXECUTION"
    JUDGE_EVALUATION = "JUDGE_EVALUATION"

    # L3 — governance
    HITL_REQUIRED = "HITL_REQUIRED"
    HITL_DECISION = "HITL_DECISION"
    JUDGE_ESCALATION = "JUDGE_ESCALATION"
    GOVERNANCE_OVERRIDE = "GOVERNANCE_OVERRIDE"
    POLICY_DECISION = "POLICY_DECISION"
    GDPR_ALERT = "GDPR_ALERT"
    INTEGRITY_ALERT = "INTEGRITY_ALERT"


#: Default tier for each event type. audit_service.py uses this so callers
#: normally don't have to specify the tier explicitly — but audit_logger.py
#: always takes an explicit tier, so a caller *can* override this when an
#: event genuinely belongs at a different tier for a specific case (e.g.
#: JUDGE_EVALUATION logged at L2 on ACCEPT, re-logged at L3 as
#: JUDGE_ESCALATION on REJECT — those are two different EventType values,
#: so no override is actually needed for that particular case).
TIER_OF_EVENT: Dict[EventType, Tier] = {
    EventType.CHAT_REQUEST: Tier.L1,
    EventType.CHAT_RESPONSE: Tier.L1,
    EventType.MODERATION_RESULT: Tier.L2,
    EventType.ROUTING_DECISION: Tier.L2,
    EventType.RAG_RETRIEVAL: Tier.L2,
    EventType.AGENT_EXECUTION: Tier.L2,
    EventType.JUDGE_EVALUATION: Tier.L2,
    EventType.HITL_REQUIRED: Tier.L3,
    EventType.HITL_DECISION: Tier.L3,
    EventType.JUDGE_ESCALATION: Tier.L3,
    EventType.GOVERNANCE_OVERRIDE: Tier.L3,
    EventType.POLICY_DECISION: Tier.L3,
    EventType.GDPR_ALERT: Tier.L3,
    EventType.INTEGRITY_ALERT: Tier.L3,
}


class HITLDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    OVERRIDDEN = "overridden"


class GovernanceFailureMode(str, Enum):
    """What to do when writing an audit event fails (DB down, etc).
    Configured via GOVERNANCE_FAILURE_MODE, per risk level — see
    risk_policy.py / audit_service.py. Never silently swallowed either way;
    FAIL_OPEN still raises a logged GovernanceAuditError internally, it
    just doesn't block the banking action."""
    FAIL_OPEN = "fail_open"      # log the error, let the workflow continue
    FAIL_CLOSED = "fail_closed"  # raise, workflow must handle/block


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def new_event_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_safe(value: Any) -> Any:
    """Unwraps Enum members to their .value so dataclass.to_dict() output
    is plain-JSON-serializable and, critically, DETERMINISTIC — the same
    logical event always serializes to the same string, which is required
    for the hash chain in integrity.py to be reproducible on verification."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _enum_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_safe(v) for v in value]
    return value


# ═══════════════════════════════════════════════════════════════════════════
# RISK / PII SUPPORT TYPES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RiskAssessment:
    """Output of risk_policy.py. Deliberately carries `reason` and
    `rule_source` so the system can always explain itself:
        intent -> risk_level -> reason -> hitl_required
    e.g. FRAUD -> CRITICAL -> "fraud-related operation" -> HITL required
    """
    risk_level: RiskLevel
    reason: str
    hitl_required: bool
    rule_source: str  # e.g. "intent:fraud", "confidence_threshold", "judge_score"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "hitl_required": self.hitl_required,
            "rule_source": self.rule_source,
        }


@dataclass
class PIIDetectionResult:
    """Output of pii_protection.py. NEVER carries raw PII values — only
    whether PII was found and which entity types, per the project's data
    minimization requirement."""
    pii_detected: bool
    entity_types: List[str] = field(default_factory=list)
    detection_method: str = "regex"  # "regex" | "presidio" | "regex+presidio"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pii_detected": self.pii_detected,
            "entity_types": sorted(self.entity_types),
            "detection_method": self.detection_method,
        }


# ═══════════════════════════════════════════════════════════════════════════
# L1 — INTERACTION EVENT
# "What interaction happened?"
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class L1InteractionEvent:
    session_id: str
    workflow_execution_id: str
    event_type: EventType

    user_id_pseudo: Optional[str] = None          # pseudonymized, never raw
    request_type: Optional[str] = None             # e.g. "chat_message"
    message_length: Optional[int] = None            # metadata only, not content
    detected_intent: Optional[str] = None
    target_agent: Optional[str] = None
    pii: Optional[PIIDetectionResult] = None
    risk_level: Optional[RiskLevel] = None
    outcome: Optional[str] = None                   # e.g. "success", "toxic_blocked"

    event_id: str = field(default_factory=new_event_id)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["pii"] = self.pii.to_dict() if self.pii else None
        return _enum_safe(d)


# ═══════════════════════════════════════════════════════════════════════════
# L2 — EXECUTION EVENT
# "How did the AI system process the request?"
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class L2ExecutionEvent:
    session_id: str
    workflow_execution_id: str
    event_type: EventType

    agent_id: Optional[str] = None
    nodes_visited: List[str] = field(default_factory=list)
    rag_used: Optional[bool] = None
    rag_documents_count: Optional[int] = None
    confidence_score: Optional[float] = None
    processing_duration_ms: Optional[int] = None
    model_info: Optional[str] = None
    judge_score: Optional[float] = None
    hitl_triggered: Optional[bool] = None
    execution_status: Optional[str] = None          # "success" | "error" | "toxic"
    error_message: Optional[str] = None              # truncated, no stack traces

    event_id: str = field(default_factory=new_event_id)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return _enum_safe(asdict(self))


# ═══════════════════════════════════════════════════════════════════════════
# L3 — GOVERNANCE EVENT
# "Was the AI allowed to make this decision automatically, and what
#  governance controls were applied?"
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class L3GovernanceEvent:
    session_id: str
    workflow_execution_id: str
    event_type: EventType

    risk_level: Optional[RiskLevel] = None
    escalation_reason: Optional[str] = None
    hitl_required: Optional[bool] = None
    hitl_request_id: Optional[str] = None
    human_decision: Optional[HITLDecision] = None
    human_approver: Optional[str] = None
    rejection_reason: Optional[str] = None
    override_reason: Optional[str] = None
    judge_result: Optional[Dict[str, Any]] = None
    policy_decision: Optional[str] = None            # "AUTO_ALLOWED" | "ESCALATED" | ...
    governance_action: Optional[str] = None

    event_id: str = field(default_factory=new_event_id)
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return _enum_safe(asdict(self))


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRITY REPORTING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class TamperedRow:
    tier: Tier
    row_id: int
    entry_id: Optional[str]
    timestamp: Optional[str]
    detail: str  # e.g. "entry_hash mismatch", "prev_hash broken"


@dataclass
class ChainVerificationReport:
    tier: str                      # "L1" | "L2" | "L3" | "ALL"
    total_rows: int = 0
    ok_rows: int = 0
    tampered: List[TamperedRow] = field(default_factory=list)
    chain_valid: bool = True
    elapsed_ms: float = 0.0
    first_broken_event: Optional[TamperedRow] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "total_rows": self.total_rows,
            "ok_rows": self.ok_rows,
            "chain_valid": self.chain_valid,
            "elapsed_ms": self.elapsed_ms,
            "tampered": [
                {
                    "tier": t.tier.value,
                    "row_id": t.row_id,
                    "entry_id": t.entry_id,
                    "timestamp": t.timestamp,
                    "detail": t.detail,
                }
                for t in self.tampered
            ],
            "first_broken_event": (
                {
                    "tier": self.first_broken_event.tier.value,
                    "row_id": self.first_broken_event.row_id,
                    "entry_id": self.first_broken_event.entry_id,
                    "timestamp": self.first_broken_event.timestamp,
                    "detail": self.first_broken_event.detail,
                }
                if self.first_broken_event
                else None
            ),
        }
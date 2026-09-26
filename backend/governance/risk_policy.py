"""
governance/risk_policy.py

Centralized governance policy for banking intents.

The policy answers:

    intent / outcome
        ↓
    risk level
        ↓
    reason
        ↓
    HITL required?

The policy is deliberately centralized so risk decisions are not
duplicated throughout the LangGraph workflow.
"""

from __future__ import annotations

import os
from typing import Optional

from governance.models import RiskAssessment, RiskLevel


# ---------------------------------------------------------------------------
# Intent-based policy
# ---------------------------------------------------------------------------

INTENT_RISK_POLICY = {
    # Critical / highly sensitive banking operations
    "fraud": (
        RiskLevel.CRITICAL,
        "fraud-related operation",
        True,
    ),
    "anti_fraud": (
        RiskLevel.CRITICAL,
        "fraud-related operation",
        True,
    ),

    "opposition": (
        RiskLevel.CRITICAL,
        "banking opposition operation",
        True,
    ),

    "credit": (
        RiskLevel.HIGH,
        "credit-related banking operation",
        True,
    ),

    "succession": (
        RiskLevel.HIGH,
        "succession-related banking operation",
        True,
    ),

    "closure": (
        RiskLevel.HIGH,
        "account closure operation",
        True,
    ),

    "account_closure": (
        RiskLevel.HIGH,
        "account closure operation",
        True,
    ),

    "rgpd": (
        RiskLevel.HIGH,
        "personal-data/GDPR-related operation",
        True,
    ),

    "gdpr": (
        RiskLevel.HIGH,
        "personal-data/GDPR-related operation",
        True,
    ),

    # Medium-risk operations
    "complaint": (
        RiskLevel.MEDIUM,
        "customer complaint",
        False,
    ),

    "incident": (
        RiskLevel.MEDIUM,
        "banking incident",
        False,
    ),

    "admin": (
        RiskLevel.MEDIUM,
        "administrative banking operation",
        False,
    ),

    "info": (
        RiskLevel.LOW,
        "general banking information request",
        False,
    ),
}


# ---------------------------------------------------------------------------
# Thresholds — configurable via environment variables (per the project
# requirement that risk mappings not be hardcoded throughout the app).
# Read once at import time; restart the process to pick up a change, same
# as every other env-based setting in this project (e.g. GOVERNANCE_DB_*).
# ---------------------------------------------------------------------------

def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


DEFAULT_CONFIDENCE_THRESHOLD = _float_env("GOVERNANCE_CONFIDENCE_THRESHOLD", 0.60)
DEFAULT_JUDGE_THRESHOLD = _float_env("GOVERNANCE_JUDGE_SCORE_THRESHOLD", 6.0)


def normalize_intent(intent: Optional[str]) -> str:
    if not intent:
        return ""

    return intent.strip().lower().replace("-", "_").replace(" ", "_")


def assess_intent(intent: Optional[str]) -> RiskAssessment:
    """
    Determine the base risk associated with an intent.
    """

    normalized = normalize_intent(intent)

    policy = INTENT_RISK_POLICY.get(normalized)

    if policy:
        risk, reason, hitl = policy

        return RiskAssessment(
            risk_level=risk,
            reason=reason,
            hitl_required=hitl,
            rule_source=f"intent:{normalized}",
        )

    return RiskAssessment(
        risk_level=RiskLevel.LOW,
        reason="no elevated-risk policy matched",
        hitl_required=False,
        rule_source="intent:default",
    )


def assess_confidence(
    confidence: Optional[float],
) -> Optional[RiskAssessment]:
    """
    Escalate when the model/agent confidence is too low.
    """

    if confidence is None:
        return None

    if confidence < 0:
        confidence = 0.0

    if confidence < DEFAULT_CONFIDENCE_THRESHOLD:
        return RiskAssessment(
            risk_level=RiskLevel.HIGH,
            reason=(
                f"agent confidence below threshold "
                f"({confidence:.3f} < {DEFAULT_CONFIDENCE_THRESHOLD:.3f})"
            ),
            hitl_required=True,
            rule_source="confidence_threshold",
        )

    return None


def assess_judge_score(
    judge_score: Optional[float],
) -> Optional[RiskAssessment]:
    """
    Escalate when the existing Judge evaluates the response below
    the accepted threshold.
    """

    if judge_score is None:
        return None

    if judge_score < DEFAULT_JUDGE_THRESHOLD:
        return RiskAssessment(
            risk_level=RiskLevel.HIGH,
            reason=(
                f"judge score below threshold "
                f"({judge_score:.2f} < {DEFAULT_JUDGE_THRESHOLD:.2f})"
            ),
            hitl_required=True,
            rule_source="judge_score",
        )

    return None


def combine_assessments(
    *assessments: Optional[RiskAssessment],
) -> RiskAssessment:
    """
    Combine independent risk signals.

    The most severe risk wins.

    Example:

        fraud = CRITICAL
        low confidence = HIGH

        final = CRITICAL
    """

    valid = [assessment for assessment in assessments if assessment]

    if not valid:
        return RiskAssessment(
            risk_level=RiskLevel.LOW,
            reason="no elevated-risk signal",
            hitl_required=False,
            rule_source="default",
        )

    highest = max(
        valid,
        key=lambda assessment: assessment.risk_level.severity_rank,
    )

    hitl_required = any(
        assessment.hitl_required
        for assessment in valid
    )

    reasons = []
    sources = []

    for assessment in valid:
        if assessment.reason not in reasons:
            reasons.append(assessment.reason)

        if assessment.rule_source not in sources:
            sources.append(assessment.rule_source)

    return RiskAssessment(
        risk_level=highest.risk_level,
        reason="; ".join(reasons),
        hitl_required=hitl_required,
        rule_source=" + ".join(sources),
    )


def assess_request(
    intent: Optional[str] = None,
    confidence: Optional[float] = None,
    judge_score: Optional[float] = None,
) -> RiskAssessment:
    """
    Main policy entry point.

    Combines:

        intent risk
        +
        confidence risk
        +
        judge risk
    """

    return combine_assessments(
        assess_intent(intent),
        assess_confidence(confidence),
        assess_judge_score(judge_score),
    )
"""
tests/governance/test_risk_policy.py
=======================================
Covers spec item 17 "Risk-policy tests": representative banking intents
and their expected risk levels, per spec section 6's examples:
    FRAUD -> CRITICAL -> fraud-related operation -> HITL required
    LOW CONFIDENCE -> HIGH -> confidence below threshold -> HITL required
"""

from __future__ import annotations

import pytest

from governance.models import RiskLevel
from governance.risk_policy import assess_request, combine_assessments, RiskAssessment


class TestIntentRiskMapping:
    @pytest.mark.parametrize("intent,expected_level", [
        ("fraud", RiskLevel.CRITICAL),
        ("opposition", RiskLevel.CRITICAL),
        ("closure", RiskLevel.HIGH),
        ("credit", RiskLevel.HIGH),
        ("succession", RiskLevel.HIGH),
        ("rgpd", RiskLevel.HIGH),
        ("info", RiskLevel.LOW),
        ("balance_inquiry", RiskLevel.LOW),
    ])
    def test_intent_maps_to_expected_risk(self, intent, expected_level):
        result = assess_request(intent=intent, confidence=0.95, judge_score=9.0)
        assert result.risk_level == expected_level, (
            f"intent={intent!r} expected {expected_level}, got {result.risk_level} "
            f"(reason: {result.reason})"
        )

    def test_fraud_always_requires_hitl(self):
        result = assess_request(intent="fraud", confidence=0.99, judge_score=10.0)
        assert result.hitl_required is True
        assert "fraud" in result.reason.lower()

    def test_low_risk_intent_does_not_require_hitl_by_default(self):
        result = assess_request(intent="info", confidence=0.95, judge_score=9.0)
        assert result.hitl_required is False

    def test_explainability_chain_present(self):
        """intent -> risk_level -> reason -> hitl_required must all be
        populated and traceable to a rule_source, per spec section 6."""
        result = assess_request(intent="fraud", confidence=0.9, judge_score=9.0)
        assert result.risk_level is not None
        assert result.reason
        assert result.rule_source


class TestConfidenceThreshold:
    def test_low_confidence_escalates_to_high(self, monkeypatch):
        monkeypatch.setenv("GOVERNANCE_CONFIDENCE_THRESHOLD", "0.75")
        # reload module-level threshold constants
        import importlib
        import governance.risk_policy as rp
        importlib.reload(rp)

        result = rp.assess_request(intent="info", confidence=0.5, judge_score=9.0)
        assert result.risk_level.severity_rank >= RiskLevel.HIGH.severity_rank
        assert result.hitl_required is True
        assert "confidence" in result.reason.lower()

        importlib.reload(rp)  # restore defaults for other tests

    def test_high_confidence_does_not_trigger_threshold_escalation(self):
        result = assess_request(intent="info", confidence=0.95, judge_score=9.0)
        assert "confidence" not in result.reason.lower()


class TestJudgeScoreThreshold:
    def test_low_judge_score_escalates(self):
        result = assess_request(intent="info", confidence=0.95, judge_score=3.0)
        assert result.risk_level.severity_rank >= RiskLevel.HIGH.severity_rank
        assert result.hitl_required is True

    def test_high_judge_score_no_escalation_from_score_alone(self):
        result = assess_request(intent="info", confidence=0.95, judge_score=9.0)
        assert result.risk_level == RiskLevel.LOW


class TestRiskCombination:
    def test_combine_takes_most_severe(self):
        low = RiskAssessment(risk_level=RiskLevel.LOW, reason="baseline", hitl_required=False, rule_source="test")
        critical = RiskAssessment(risk_level=RiskLevel.CRITICAL, reason="fraud", hitl_required=True, rule_source="test")
        combined = combine_assessments(low, critical)
        assert combined.risk_level == RiskLevel.CRITICAL
        assert combined.hitl_required is True

    def test_combine_single_assessment_passthrough(self):
        only = RiskAssessment(risk_level=RiskLevel.MEDIUM, reason="x", hitl_required=False, rule_source="test")
        combined = combine_assessments(only)
        assert combined.risk_level == RiskLevel.MEDIUM


class TestUnknownIntent:
    def test_unknown_intent_defaults_to_low(self):
        """DOCUMENTED DESIGN CHOICE, not a bug: an intent the policy
        table has never seen currently defaults to LOW risk ("no
        elevated-risk policy matched" in governance/risk_policy.py's
        assess_intent()). This test pins down that actual behavior so a
        future change to it is a deliberate decision, not an accidental
        regression. Worth discussing for production: a new/unrecognized
        banking intent arguably warrants at least MEDIUM by default
        (treating "we don't know how risky this is" as different from
        "this is known to be low-risk") -- flagged here rather than
        silently changed, since it changes real escalation behavior.
        """
        result = assess_request(intent="some_totally_new_intent_xyz", confidence=0.9, judge_score=9.0)
        assert result.risk_level == RiskLevel.LOW
        assert result.reason


"""
tests/governance/test_hitl_governance.py
===========================================
Covers spec item 17 "HITL tests":
    - HITL request -> L3 event
    - approval -> L3 event
    - rejection -> L3 event
(plus override, which the original HITLGate had no equivalent for)

Also covers backward compatibility: the original 4-positional-argument
call shape must keep working unchanged, since workflow/langgraph_workflow.py
and app.py both call it that way.
"""

from __future__ import annotations

import pytest

from governance.audit_schema import connection_scope
from security.hitl_gate import HITLGate


def _l3_rows_for_session(session_id: str) -> list[dict]:
    with connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_type, hitl_request_id, risk_level, escalation_reason, "
                "human_decision, human_approver, rejection_reason, override_reason, "
                "governance_action "
                "FROM audit_l3_governance WHERE session_id = %s ORDER BY id ASC",
                (session_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


@pytest.mark.asyncio
class TestHITLRequestEmitsL3:
    async def test_legacy_call_shape_still_works(self, clean_db):
        """The exact 4-positional-arg call shape used throughout
        workflow/langgraph_workflow.py and app.py must keep working
        unchanged."""
        gate = HITLGate()
        result = await gate.request_approval("sess-legacy-1", "AG09", "contexte", 0.5)
        assert set(result.keys()) == {"status", "request_id"}
        assert result["status"] == "pending"

    async def test_request_creates_l3_hitl_required_event(self, clean_db):
        gate = HITLGate()
        result = await gate.request_approval(
            "sess-hitl-req-1", "AG09", "Transaction suspecte", 0.4,
            reason="montant elevé", risk_level="CRITICAL",
        )

        rows = _l3_rows_for_session("sess-hitl-req-1")
        assert len(rows) == 1
        assert rows[0]["event_type"] == "HITL_REQUIRED"
        assert rows[0]["hitl_request_id"] == result["request_id"]
        assert rows[0]["risk_level"] == "CRITICAL"
        assert rows[0]["escalation_reason"] == "montant elevé"

    async def test_pending_requests_still_tracked_in_memory(self, clean_db):
        """The in-memory pending_requests dict behavior is unchanged --
        this is what /api/hitl/pending reads."""
        gate = HITLGate()
        result = await gate.request_approval("sess-hitl-mem-1", "AG10", "ctx", 0.6)
        assert result["request_id"] in gate.pending_requests
        assert gate.pending_requests[result["request_id"]]["status"] == "pending"


@pytest.mark.asyncio
class TestApprovalEmitsL3:
    async def test_approve_creates_l3_hitl_decision_event(self, clean_db):
        gate = HITLGate()
        req = await gate.request_approval("sess-approve-1", "AG09", "ctx", 0.5)
        await gate.approve(req["request_id"], "supervisor_karim")

        rows = _l3_rows_for_session("sess-approve-1")
        event_types = [r["event_type"] for r in rows]
        assert "HITL_REQUIRED" in event_types
        assert "HITL_DECISION" in event_types

        decision_row = next(r for r in rows if r["event_type"] == "HITL_DECISION")
        assert decision_row["human_decision"] == "approved"
        assert decision_row["human_approver"] == "supervisor_karim"
        assert decision_row["hitl_request_id"] == req["request_id"]

    async def test_approve_updates_in_memory_status(self, clean_db):
        gate = HITLGate()
        req = await gate.request_approval("sess-approve-2", "AG09", "ctx", 0.5)
        await gate.approve(req["request_id"], "supervisor_x")
        assert gate.pending_requests[req["request_id"]]["status"] == "approved"

    async def test_approve_unknown_request_id_does_not_raise(self, clean_db):
        """Approving a request_id this gate instance never created (e.g.
        stale, or from a different process) must not crash -- it should
        be handled gracefully, since a rogue/duplicate id should not take
        down the endpoint."""
        gate = HITLGate()
        result = await gate.approve("does-not-exist", "supervisor")
        assert result["status"] == "approved"


@pytest.mark.asyncio
class TestRejectionEmitsL3:
    async def test_reject_creates_l3_hitl_decision_event(self, clean_db):
        gate = HITLGate()
        req = await gate.request_approval("sess-reject-1", "AG10", "ctx", 0.5)
        await gate.reject(req["request_id"], "documentation insuffisante", approver="supervisor_amal")

        rows = _l3_rows_for_session("sess-reject-1")
        decision_row = next(r for r in rows if r["event_type"] == "HITL_DECISION")
        assert decision_row["human_decision"] == "rejected"
        assert decision_row["rejection_reason"] == "documentation insuffisante"
        assert decision_row["human_approver"] == "supervisor_amal"

    async def test_reject_updates_in_memory_status(self, clean_db):
        gate = HITLGate()
        req = await gate.request_approval("sess-reject-2", "AG10", "ctx", 0.5)
        await gate.reject(req["request_id"], "raison")
        assert gate.pending_requests[req["request_id"]]["status"] == "rejected"


@pytest.mark.asyncio
class TestOverrideEmitsL3:
    async def test_override_creates_l3_governance_override_event(self, clean_db):
        gate = HITLGate()
        req = await gate.request_approval("sess-override-1", "AG06", "ctx", 0.9, risk_level="CRITICAL")
        await gate.override(req["request_id"], "compliance_officer_nadia", "revue manuelle effectuee hors ligne")

        rows = _l3_rows_for_session("sess-override-1")
        override_row = next(r for r in rows if r["event_type"] == "GOVERNANCE_OVERRIDE")
        assert override_row["human_decision"] == "overridden"
        assert override_row["human_approver"] == "compliance_officer_nadia"
        assert override_row["override_reason"] == "revue manuelle effectuee hors ligne"


@pytest.mark.asyncio
class TestFullLifecycleTraceability:
    async def test_request_to_decision_share_same_request_id(self, clean_db):
        """The core traceability property the whole HITL instrumentation
        exists for: HITL_REQUIRED and HITL_DECISION for the same human
        decision must carry the SAME hitl_request_id, so a compliance
        reviewer can link the AI's escalation to the human's response."""
        gate = HITLGate()
        req = await gate.request_approval("sess-trace-1", "AG09", "ctx", 0.5, risk_level="CRITICAL")
        await gate.approve(req["request_id"], "supervisor")

        rows = _l3_rows_for_session("sess-trace-1")
        request_ids = {r["hitl_request_id"] for r in rows}
        assert request_ids == {req["request_id"]}

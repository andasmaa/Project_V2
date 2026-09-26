"""
tests/governance/test_audit_events.py
========================================
Covers spec item 17 "Audit-event tests": important workflow stages
generate the expected audit events. Runs the REAL, fully-instrumented
LangGraph workflow (workflow/langgraph_workflow.py) with stub LLM/RAG
agents standing in for Groq/ChromaDB, and asserts on what actually landed
in Postgres -- not on mocked calls.
"""

from __future__ import annotations

import pytest

from governance.audit_schema import connection_scope
from workflow.langgraph_workflow import BankAgentWorkflow


def _events_for_session(table: str, session_id: str) -> list[dict]:
    with connection_scope() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM {table} WHERE session_id = %s ORDER BY id ASC",
                (session_id,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


@pytest.fixture
def workflow():
    return BankAgentWorkflow()


@pytest.mark.asyncio
class TestNormalRequestLifecycle:
    async def test_full_event_sequence_for_simple_request(self, clean_db, workflow):
        result = await workflow.process_message(
            "Quel est mon solde ?", "chat_user", "sess-audit-normal-1"
        )
        assert result["success"] is True

        l1 = _events_for_session("audit_l1_interaction", "sess-audit-normal-1")
        l2 = _events_for_session("audit_l2_execution", "sess-audit-normal-1")

        l1_types = [e["event_type"] for e in l1]
        l2_types = [e["event_type"] for e in l2]

        assert l1_types == ["CHAT_REQUEST", "CHAT_RESPONSE"]
        assert l2_types == [
            "MODERATION_RESULT",
            "ROUTING_DECISION",
            "RAG_RETRIEVAL",
            "AGENT_EXECUTION",
            "JUDGE_EVALUATION",
        ]

    async def test_all_events_share_one_workflow_execution_id(self, clean_db, workflow):
        result = await workflow.process_message(
            "Quel est mon solde ?", "chat_user", "sess-audit-correlation-1"
        )
        wf_id = result["workflow_execution_id"]
        assert wf_id

        l1 = _events_for_session("audit_l1_interaction", "sess-audit-correlation-1")
        l2 = _events_for_session("audit_l2_execution", "sess-audit-correlation-1")

        assert all(e["workflow_execution_id"] == wf_id for e in l1)
        assert all(e["workflow_execution_id"] == wf_id for e in l2)


@pytest.mark.asyncio
class TestModerationBlockedLifecycle:
    async def test_toxic_message_short_circuits_before_router(self, clean_db, workflow):
        result = await workflow.process_message(
            "INSULT_TEST message toxique", "chat_user", "sess-audit-toxic-1"
        )

        l2 = _events_for_session("audit_l2_execution", "sess-audit-toxic-1")
        l2_types = [e["event_type"] for e in l2]

        assert l2_types == ["MODERATION_RESULT"]
        assert l2[0]["execution_status"] == "blocked"

        l1 = _events_for_session("audit_l1_interaction", "sess-audit-toxic-1")
        assert [e["event_type"] for e in l1] == ["CHAT_REQUEST", "CHAT_RESPONSE"]


@pytest.mark.asyncio
class TestHighRiskLifecycle:
    async def test_fraud_request_generates_hitl_and_escalation_events(self, clean_db, workflow):
        result = await workflow.process_message(
            "URGENT_FRAUD_TEST: fraude suspectee 50000 MAD", "chat_user", "sess-audit-fraud-1"
        )
        assert result["requires_hitl"] is True
        assert result["hitl_request_id"] is not None

        l3 = _events_for_session("audit_l3_governance", "sess-audit-fraud-1")
        l3_types = [e["event_type"] for e in l3]

        assert "HITL_REQUIRED" in l3_types
        assert "JUDGE_ESCALATION" in l3_types  # the stub judge rejects fraud-test messages

        hitl_row = next(e for e in l3 if e["event_type"] == "HITL_REQUIRED")
        assert hitl_row["hitl_request_id"] == result["hitl_request_id"]
        assert hitl_row["risk_level"] in ("HIGH", "CRITICAL")

    async def test_no_rag_documents_recorded_accurately(self, clean_db, workflow):
        result = await workflow.process_message(
            "NO_RAG_TEST requete sans documents", "chat_user", "sess-audit-norag-1"
        )
        l2 = _events_for_session("audit_l2_execution", "sess-audit-norag-1")
        rag_row = next(e for e in l2 if e["event_type"] == "RAG_RETRIEVAL")
        assert rag_row["rag_used"] is False
        assert rag_row["rag_documents_count"] == 0


@pytest.mark.asyncio
class TestDataMinimizationInEvents:
    async def test_raw_message_never_stored_in_l1(self, clean_db, workflow):
        secret_message = "Mon email est ultra.secret.test@example.com et mon IBAN MA64011519000001205000534921"
        await workflow.process_message(secret_message, "chat_user", "sess-audit-pii-1")

        l1 = _events_for_session("audit_l1_interaction", "sess-audit-pii-1")
        for row in l1:
            serialized = str(row)
            assert "ultra.secret.test@example.com" not in serialized
            assert "MA64011519000001205000534921" not in serialized

        request_row = next(e for e in l1 if e["event_type"] == "CHAT_REQUEST")
        assert request_row["pii_detected"] is True
        assert "EMAIL" in (request_row["pii_entity_types"] or [])
        assert "IBAN" in (request_row["pii_entity_types"] or [])
        assert request_row["message_length"] == len(secret_message)

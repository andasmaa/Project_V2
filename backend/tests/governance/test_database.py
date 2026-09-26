"""
tests/governance/test_database.py
====================================
Covers spec item 17 "Database tests": insertion/retrieval and hash-chain
persistence, plus the append-only guarantees the whole integrity model
depends on (RLS + REVOKE).
"""

from __future__ import annotations

import psycopg2
import pytest

from governance.audit_schema import (
    TABLE_NAMES,
    connection_scope,
    get_db_config,
    schema_exists,
)
from governance.audit_service import AuditService
from governance.models import EventType, Tier


class TestSchemaSetup:
    def test_all_three_tables_exist(self):
        assert schema_exists() is True

    def test_table_names_match_spec(self):
        assert TABLE_NAMES[Tier.L1] == "audit_l1_interaction"
        assert TABLE_NAMES[Tier.L2] == "audit_l2_execution"
        assert TABLE_NAMES[Tier.L3] == "audit_l3_governance"


class TestInsertionAndRetrieval:
    def test_l1_insert_and_read_back(self, clean_db):
        svc = AuditService()
        event_id = svc.log_request(
            session_id="sess-db-l1-1",
            workflow_execution_id="wf-db-1",
            user_id_pseudo="user_test",
            message="test message",
            intent="info",
        )
        assert event_id is not None

        with connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT event_id, session_id, event_type FROM audit_l1_interaction WHERE event_id = %s",
                    (event_id,),
                )
                row = cur.fetchone()
        assert row is not None
        assert row[0] == event_id
        assert row[1] == "sess-db-l1-1"
        assert row[2] == "CHAT_REQUEST"

    def test_l2_insert_and_read_back(self, clean_db):
        svc = AuditService()
        event_id = svc.log_execution(
            session_id="sess-db-l2-1",
            workflow_execution_id="wf-db-2",
            event_type=EventType.AGENT_EXECUTION,
            agent_id="AG02",
            confidence_score=0.87,
            execution_status="success",
        )
        assert event_id is not None

        with connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT agent_id, confidence_score FROM audit_l2_execution WHERE event_id = %s",
                    (event_id,),
                )
                row = cur.fetchone()
        assert row[0] == "AG02"
        assert abs(row[1] - 0.87) < 1e-9

    def test_l3_insert_and_read_back(self, clean_db):
        svc = AuditService()
        event_id = svc.log_governance(
            session_id="sess-db-l3-1",
            workflow_execution_id="wf-db-3",
            event_type=EventType.POLICY_DECISION,
            governance_action="TEST_ACTION",
        )
        assert event_id is not None

        with connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT governance_action FROM audit_l3_governance WHERE event_id = %s",
                    (event_id,),
                )
                row = cur.fetchone()
        assert row[0] == "TEST_ACTION"

    def test_event_ids_are_unique(self, clean_db):
        svc = AuditService()
        ids = [
            svc.log_request(
                session_id="sess-db-unique-1",
                workflow_execution_id="wf-db-unique",
                user_id_pseudo=None,
                message="msg",
            )
            for _ in range(10)
        ]
        assert len(set(ids)) == 10


class TestHashChainPersistence:
    def test_prev_hash_and_entry_hash_persisted(self, clean_db):
        svc = AuditService()
        id1 = svc.log_request(
            session_id="sess-db-chain-1", workflow_execution_id="wf-1",
            user_id_pseudo=None, message="first",
        )
        id2 = svc.log_request(
            session_id="sess-db-chain-1", workflow_execution_id="wf-1",
            user_id_pseudo=None, message="second",
        )

        with connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT event_id, prev_hash, entry_hash FROM audit_l1_interaction "
                    "WHERE session_id = 'sess-db-chain-1' ORDER BY id ASC"
                )
                rows = cur.fetchall()

        assert len(rows) == 2
        row1, row2 = rows
        # First row in an otherwise-empty chain: prev_hash is the literal
        # GENESIS_HASH sentinel ("0"*64), not SQL NULL -- a deliberate
        # design choice (see governance/integrity.py's GENESIS_HASH) that
        # avoids NULL-handling edge cases in the hash computation itself.
        assert row1[1] == "0" * 64
        assert row1[2]  # entry_hash is set
        assert row2[1] == row1[2]  # second row's prev_hash == first row's entry_hash
        assert row2[2] != row1[2]  # distinct hashes

    def test_chain_survives_across_service_instances(self, clean_db):
        """A new AuditService/AuditLogger instance (e.g. a new request in
        a new worker process) must correctly continue an existing chain,
        not start a fresh one -- the chain lives in the DB, not in
        process memory."""
        svc1 = AuditService()
        svc1.log_request(session_id="sess-db-persist-1", workflow_execution_id="wf-1", user_id_pseudo=None, message="a")

        svc2 = AuditService()  # simulates a fresh process/request
        svc2.log_request(session_id="sess-db-persist-1", workflow_execution_id="wf-1", user_id_pseudo=None, message="b")

        with connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT prev_hash, entry_hash FROM audit_l1_interaction "
                    "WHERE session_id = 'sess-db-persist-1' ORDER BY id ASC"
                )
                rows = cur.fetchall()

        assert rows[1][0] == rows[0][1]  # chain correctly continued, not restarted


class TestAppendOnlyGuarantee:
    """These deliberately connect AS THE APPLICATION ROLE (audit_writer,
    via get_db_config()), not the test superuser -- proving the
    restriction the production app itself is actually subject to."""

    def test_update_denied_for_app_role(self, clean_db):
        svc = AuditService()
        event_id = svc.log_request(
            session_id="sess-db-rls-1", workflow_execution_id="wf-1",
            user_id_pseudo=None, message="test",
        )

        cfg = get_db_config()
        conn = psycopg2.connect(cfg.to_dsn())
        try:
            with conn.cursor() as cur:
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute(
                        "UPDATE audit_l1_interaction SET outcome = 'hacked' WHERE event_id = %s",
                        (event_id,),
                    )
            conn.rollback()
        finally:
            conn.close()

    def test_delete_denied_for_app_role(self, clean_db):
        svc = AuditService()
        event_id = svc.log_request(
            session_id="sess-db-rls-2", workflow_execution_id="wf-1",
            user_id_pseudo=None, message="test",
        )

        cfg = get_db_config()
        conn = psycopg2.connect(cfg.to_dsn())
        try:
            with conn.cursor() as cur:
                with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                    cur.execute(
                        "DELETE FROM audit_l1_interaction WHERE event_id = %s",
                        (event_id,),
                    )
            conn.rollback()
        finally:
            conn.close()

    def test_select_and_insert_still_work_for_app_role(self, clean_db):
        """The append-only lockdown must not be so strict it breaks
        normal operation -- SELECT and INSERT must still work fine."""
        svc = AuditService()
        event_id = svc.log_request(
            session_id="sess-db-rls-3", workflow_execution_id="wf-1",
            user_id_pseudo=None, message="test",
        )
        assert event_id is not None

        cfg = get_db_config()
        conn = psycopg2.connect(cfg.to_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT event_id FROM audit_l1_interaction WHERE event_id = %s", (event_id,))
                assert cur.fetchone() is not None
        finally:
            conn.close()

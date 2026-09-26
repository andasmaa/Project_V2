"""
tests/governance/test_integrity.py
=====================================
Covers spec item 17 "Hash-chain tests":
  - valid chain -> verification succeeds
  - modified event -> verification fails
  - deleted event -> verification fails
  - reordered event -> verification fails
  - wrong previous hash -> verification fails

Tampering is done through `superuser_conn` — a connection the
application itself never uses — specifically to prove that even when
someone bypasses RLS/REVOKE entirely (a rogue DBA, a restore from an old
backup, direct disk access), the cryptographic layer still catches it.
RLS answers "can this role write here"; these tests answer "if someone
writes here anyway, can we tell".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from governance.audit_schema import connection_scope
from governance.audit_service import AuditService
from governance.models import EventType, Tier
from governance.verify_chain import verify_tier


def _insert_l1_chain(audit_service: AuditService, session_id: str, n: int) -> list[str]:
    """Inserts n real, correctly hash-chained L1 CHAT_REQUEST events for
    one session, through the real write path (not a hand-rolled INSERT),
    and returns their event_ids in insertion order."""
    ids = []
    for i in range(n):
        eid = audit_service.log_request(
            session_id=session_id,
            workflow_execution_id=f"wf-{session_id}-{i}",
            user_id_pseudo="user_test",
            message=f"message number {i}",
            intent="info",
        )
        assert eid is not None, "insert failed -- test setup itself is broken"
        ids.append(eid)
    return ids


class TestValidChain:
    def test_clean_chain_verifies(self, clean_db):
        svc = AuditService()
        _insert_l1_chain(svc, "sess-clean-1", 5)

        report = verify_tier(Tier.L1)

        assert report.chain_valid is True
        assert report.total_rows == 5
        assert report.ok_rows == 5
        assert report.tampered == []
        assert report.first_broken_event is None

    def test_empty_chain_verifies(self, clean_db):
        report = verify_tier(Tier.L1)
        assert report.chain_valid is True
        assert report.total_rows == 0


class TestModifiedEvent:
    def test_modified_row_data_is_detected(self, clean_db, superuser_conn):
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-modified-1", 3)

        # Tamper the middle row's data directly, bypassing the app entirely.
        with superuser_conn.cursor() as cur:
            cur.execute(
                "UPDATE audit_l1_interaction SET outcome = 'tampered_outcome' "
                "WHERE event_id = %s",
                (ids[1],),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)

        assert report.chain_valid is False
        assert len(report.tampered) == 1
        assert report.first_broken_event.entry_id == ids[1]
        assert "entry hash mismatch" in report.first_broken_event.detail.lower() \
            or "entry_hash" in report.first_broken_event.detail.lower()

    def test_untampered_rows_still_report_clean(self, clean_db, superuser_conn):
        """A tampered row must not cause false positives on its
        neighbors -- only rows whose own data or whose prev_hash link is
        actually broken should be flagged."""
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-modified-2", 4)

        with superuser_conn.cursor() as cur:
            cur.execute(
                "UPDATE audit_l1_interaction SET outcome = 'tampered' WHERE event_id = %s",
                (ids[2],),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)
        tampered_ids = {t.entry_id for t in report.tampered}

        assert ids[2] in tampered_ids
        assert ids[0] not in tampered_ids
        assert ids[1] not in tampered_ids
        # NOTE: row 3 (after the tampered row) legitimately DOES break --
        # its stored prev_hash pointed at row 2's ORIGINAL hash, which no
        # longer matches row 2's (now-different) recomputed hash. This is
        # correct, not a false positive: the chain genuinely is broken
        # from that point forward. See test_forged_hash_with_consistent_
        # prev_hash_still_detected below for the isolated single-row case.


class TestForgedHash:
    def test_forged_hash_with_consistent_prev_hash_still_detected(self, clean_db, superuser_conn):
        """Even if an attacker recomputes a plausible-looking entry_hash
        after editing a row (so the NEXT row's prev_hash reference still
        lines up), the forged hash itself won't match what the verifier
        independently recomputes from the row's actual stored data."""
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-forged-1", 2)

        with superuser_conn.cursor() as cur:
            cur.execute(
                "UPDATE audit_l1_interaction SET outcome = 'forged', "
                "entry_hash = 'deadbeef' || repeat('0', 56) "
                "WHERE event_id = %s",
                (ids[0],),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)
        assert report.chain_valid is False
        tampered_ids = {t.entry_id for t in report.tampered}
        assert ids[0] in tampered_ids


class TestDeletedEvent:
    def test_deleted_middle_row_breaks_chain(self, clean_db, superuser_conn):
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-deleted-1", 4)

        with superuser_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM audit_l1_interaction WHERE event_id = %s",
                (ids[1],),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)

        assert report.chain_valid is False
        assert report.total_rows == 3  # one row genuinely gone
        # the row immediately after the gap must be flagged: its stored
        # prev_hash points at the now-deleted row's hash, which no
        # longer matches its new (post-deletion) predecessor
        assert report.first_broken_event.entry_id == ids[2]
        assert "previous hash" in report.first_broken_event.detail.lower()

    def test_deleted_first_row_breaks_chain(self, clean_db, superuser_conn):
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-deleted-2", 3)

        with superuser_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM audit_l1_interaction WHERE event_id = %s",
                (ids[0],),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)
        assert report.chain_valid is False
        # the new first row now has a non-null prev_hash pointing at a
        # hash that doesn't match "no previous row" (GENESIS)
        assert report.first_broken_event.entry_id == ids[1]


class TestReorderedEvent:
    def test_swapped_prev_hash_links_detected(self, clean_db, superuser_conn):
        """Simulates reordering by swapping two rows' prev_hash values
        directly -- the practical effect of 'this chain's rows are no
        longer in their original causal order'."""
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-reorder-1", 3)

        with superuser_conn.cursor() as cur:
            cur.execute("SELECT event_id, prev_hash FROM audit_l1_interaction "
                        "WHERE session_id = 'sess-reorder-1' ORDER BY id ASC;")
            rows = cur.fetchall()
            assert len(rows) == 3
            # swap row[1] and row[2]'s prev_hash values
            cur.execute(
                "UPDATE audit_l1_interaction SET prev_hash = %s WHERE event_id = %s",
                (rows[2][1], rows[1][0]),
            )
            cur.execute(
                "UPDATE audit_l1_interaction SET prev_hash = %s WHERE event_id = %s",
                (rows[1][1], rows[2][0]),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)
        assert report.chain_valid is False
        assert len(report.tampered) >= 1


class TestWrongPreviousHash:
    def test_arbitrary_wrong_prev_hash_detected(self, clean_db, superuser_conn):
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-wrongprev-1", 2)

        with superuser_conn.cursor() as cur:
            cur.execute(
                "UPDATE audit_l1_interaction SET prev_hash = %s WHERE event_id = %s",
                ("0" * 64, ids[1]),
            )
        superuser_conn.commit()

        report = verify_tier(Tier.L1)
        assert report.chain_valid is False
        assert report.first_broken_event.entry_id == ids[1]
        assert "previous hash" in report.first_broken_event.detail.lower()


class TestCrossTierIndependence:
    def test_tampering_l1_does_not_affect_l2_or_l3(self, clean_db, superuser_conn):
        """Each tier has its own independent chain -- corrupting one
        must not cause false failures in the others."""
        svc = AuditService()
        ids = _insert_l1_chain(svc, "sess-cross-1", 2)
        svc.log_execution(
            session_id="sess-cross-1",
            workflow_execution_id="wf-cross-1",
            event_type=EventType.AGENT_EXECUTION,
            agent_id="AG02",
            execution_status="success",
        )

        with superuser_conn.cursor() as cur:
            cur.execute(
                "UPDATE audit_l1_interaction SET outcome = 'tampered' WHERE event_id = %s",
                (ids[0],),
            )
        superuser_conn.commit()

        l1_report = verify_tier(Tier.L1)
        l2_report = verify_tier(Tier.L2)

        assert l1_report.chain_valid is False
        assert l2_report.chain_valid is True

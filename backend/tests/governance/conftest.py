"""
tests/governance/conftest.py
==============================
Shared fixtures for the governance test suite.

Requires a real PostgreSQL instance reachable via the usual GOVERNANCE_DB_*
env vars (see .env.governance.example). These tests intentionally hit a
real database rather than mocking psycopg2 — the whole point of this
layer is the interaction between deterministic hashing, Postgres storage,
and RLS, and mocks would hide exactly the bugs that matter (see the
inline comments in governance/integrity.py and governance/audit_logger.py
about timestamp/numeric-type round-tripping, both found via real-DB
testing, not by inspection).

A second, PRIVILEGED connection (TEST_DB_SUPERUSER_DSN) is used ONLY by
the `clean_db` fixture to wipe tables between tests. This is deliberate:
the application role (audit_writer) is intentionally denied UPDATE/DELETE
by governance/audit_schema.py's RLS + REVOKE (that's the whole point of
the append-only design) — so cleaning up test data between runs requires
a role the tests use only for setup/teardown, never for anything the
governance layer itself does.
"""

from __future__ import annotations

import os

import psycopg2
import pytest

from governance.audit_schema import initialize_schema, TABLE_NAMES


def _superuser_dsn() -> str:
    return os.getenv(
        "TEST_DB_SUPERUSER_DSN",
        "postgresql://postgres:postgres@localhost:5432/banking_audit",
    )


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Runs once per test session: makes sure the governance schema
    exists. Does NOT wipe existing data at session start — individual
    tests that need a clean chain use the `clean_db` fixture instead, so
    this suite is safe to run against a database that already has other
    data in it (e.g. from manual exploration)."""
    initialize_schema(drop_existing=False)
    yield


@pytest.fixture
def clean_db():
    """Wipes all three audit tables via a privileged connection (NOT the
    restricted audit_writer role — see module docstring) before the
    test runs. Use this for any test that asserts on exact row counts or
    needs a pristine hash chain (chain tests especially: a hash chain's
    validity depends on knowing exactly which row is first)."""
    conn = psycopg2.connect(_superuser_dsn())
    try:
        with conn.cursor() as cur:
            for table in TABLE_NAMES.values():
                cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;")
        conn.commit()
    finally:
        conn.close()
    yield


@pytest.fixture
def superuser_conn():
    """A raw privileged connection, for tests that need to simulate
    tampering (e.g. 'a rogue DBA edits a row directly') to prove the
    hash-chain verifier catches it. The application's own RLS/REVOKE
    setup already prevents audit_writer from doing this — these tests
    exist to prove that even bypassing that layer entirely still gets
    caught by the cryptographic layer underneath it."""
    conn = psycopg2.connect(_superuser_dsn())
    yield conn
    conn.close()

@pytest.fixture(autouse=True)
def _stub_llm_agents(monkeypatch):
    """Deterministic, network-free stand-ins for the two LLM calls the
    governance test-suite depends on the *content* of. Without this,
    moderation/judge fall back to non-deterministic behavior whenever
    Groq isn't configured — which is exactly what produced the three
    failures this fixture fixes."""
    import json
    from agents.moderation_agent import ModerationAgent
    from agents.judge_agent import JudgeAgent

    async def fake_check_toxicity(self, message: str):
        toxic = "INSULT_TEST" in message
        return {"score": 0.95 if toxic else 0.05, "is_toxic": toxic, "reason": "test stub"}

    async def fake_call_llm(self, prompt, system=None, rag_context=None,
                             max_tokens=150, temperature=0.3):
        low_score = "URGENT_FRAUD_TEST" in prompt
        result = {"score_total": 3 if low_score else 9,
                  "decision": "REJECT" if low_score else "ACCEPT",
                  "factualite": 3 if low_score else 9, "coherence": 3 if low_score else 9}
        return json.dumps(result)

    monkeypatch.setattr(ModerationAgent, "check_toxicity", fake_check_toxicity)
    monkeypatch.setattr(JudgeAgent, "call_llm", fake_call_llm)

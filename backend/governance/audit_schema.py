"""
governance/audit_schema.py
============================
Single source of truth for:
  1. How the governance layer connects to PostgreSQL (env-based config,
     with an optional Vault lookup that mirrors the pattern already used by
     backend/security/vault_loader.py + backend/database.py).
  2. The DDL for the three audit tables (audit_l1_interaction,
     audit_l2_execution, audit_l3_governance).

This resolves the two concrete inconsistencies identified in the original
audit prototype:
  - audit_logger.py had one hardcoded DB connection, verify_chain.py had
    a second, different, hardcoded DB connection.
  - verify_chain.py queried tables named l1_interaction_logs /
    l2_execution_logs / l3_governance_logs, which schema.sql never created
    (schema.sql creates audit_l1_interaction / audit_l2_execution /
    audit_l3_governance).

Every other governance module imports TABLE_NAMES and get_connection() (or
connection_scope()) from here instead of hardcoding either.
"""

from __future__ import annotations

import argparse
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional
from dotenv import load_dotenv

load_dotenv()

import psycopg2
import psycopg2.extensions
import psycopg2.sql

from governance.models import Tier

logger = logging.getLogger("governance.audit_schema")


# ═══════════════════════════════════════════════════════════════════════════
# TABLE NAMES — single source of truth
# ═══════════════════════════════════════════════════════════════════════════

TABLE_NAMES: dict[Tier, str] = {
    Tier.L1: "audit_l1_interaction",
    Tier.L2: "audit_l2_execution",
    Tier.L3: "audit_l3_governance",
}


class GovernanceDBError(RuntimeError):
    """Raised for any governance-DB-layer failure (connection, config,
    schema init). Callers decide fail-open/fail-closed behavior based on
    GovernanceFailureMode — this exception is never swallowed silently."""


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

def _load_vault_config() -> dict:
    """Best-effort lookup of a 'governance_db' secret in Vault, mirroring
    security/vault_loader.py's get_database_config(). Never raises — if
    Vault is unavailable or the secret doesn't exist, we fall back to plain
    environment variables, exactly like backend/database.py already does
    for the SQLite path."""
    try:
        from security.vault_loader import get_secret  # existing project module
        return get_secret("governance_db") or {}
    except Exception as exc:  # pragma: no cover - vault is optional
        logger.debug("Vault lookup for governance_db skipped: %s", exc)
        return {}


@dataclass(frozen=True)
class GovernanceDBConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    sslmode: str = "prefer"
    dsn_override: Optional[str] = None

    def to_dsn(self) -> str:
        if self.dsn_override:
            return self.dsn_override
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.dbname}?sslmode={self.sslmode}"
        )

    def safe_repr(self) -> str:
        """DSN-shaped string with the password masked, safe to log."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{self.dbname}"


def get_db_config() -> GovernanceDBConfig:
    """Resolves the governance DB connection config, in priority order:
      1. GOVERNANCE_DB_DSN env var (or a vault 'dsn' field) — full override
      2. Individual GOVERNANCE_DB_* env vars, with Vault values (if any)
         taking priority over env vars, and hardcoded defaults last.
    No password is ever hardcoded as a real default — the only literal
    default below is an empty string, forcing explicit configuration.
    """
    vault_cfg = _load_vault_config()

    dsn_override = os.getenv("GOVERNANCE_DB_DSN") or vault_cfg.get("dsn")

    return GovernanceDBConfig(
        host=vault_cfg.get("host") or os.getenv("GOVERNANCE_DB_HOST", "localhost"),
        port=int(vault_cfg.get("port") or os.getenv("GOVERNANCE_DB_PORT", "5432")),
        dbname=vault_cfg.get("dbname") or os.getenv("GOVERNANCE_DB_NAME", "banking_audit"),
        user=vault_cfg.get("user") or os.getenv("GOVERNANCE_DB_USER", "audit_writer"),
        password=vault_cfg.get("password") or os.getenv("GOVERNANCE_DB_PASSWORD", ""),
        sslmode=vault_cfg.get("sslmode") or os.getenv("GOVERNANCE_DB_SSLMODE", "prefer"),
        dsn_override=dsn_override,
    )


# ═══════════════════════════════════════════════════════════════════════════
# CONNECTION HANDLING
# ═══════════════════════════════════════════════════════════════════════════

def get_connection(config: Optional[GovernanceDBConfig] = None) -> psycopg2.extensions.connection:
    """Opens a new psycopg2 connection. Raises GovernanceDBError (never a
    bare psycopg2 exception) so callers up the stack have one exception
    type to handle regardless of the underlying driver."""
    cfg = config or get_db_config()
    try:
        return psycopg2.connect(cfg.to_dsn())
    except psycopg2.OperationalError as exc:
        raise GovernanceDBError(
            f"Could not connect to governance audit DB at {cfg.safe_repr()}: {exc}"
        ) from exc


@contextmanager
def connection_scope(config: Optional[GovernanceDBConfig] = None) -> Iterator[psycopg2.extensions.connection]:
    """Context manager: commits on success, rolls back and re-raises as
    GovernanceDBError on failure, always closes the connection. This is
    the primary way the rest of the governance layer talks to Postgres."""
    conn = get_connection(config)
    try:
        yield conn
        conn.commit()
    except Exception as exc:
        conn.rollback()
        if isinstance(exc, GovernanceDBError):
            raise
        raise GovernanceDBError(f"Governance DB operation failed: {exc}") from exc
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# DDL
# ═══════════════════════════════════════════════════════════════════════════

_DDL_DROP = """
DROP TABLE IF EXISTS audit_l3_governance  CASCADE;
DROP TABLE IF EXISTS audit_l2_execution   CASCADE;
DROP TABLE IF EXISTS audit_l1_interaction CASCADE;
"""

# NOTE ON TYPES: session_id / workflow_execution_id / event_id are TEXT
# rather than UUID. The workflow's session_id is generated with
# str(uuid.uuid4()) server-side, but app.py also accepts a client-supplied
# session_id (ChatRequest.session_id) that is not guaranteed to be a valid
# UUID. Using TEXT avoids brittle runtime cast errors for a column whose
# only real requirement is "stable identifier to group events by", not
# "valid UUID".

_DDL_L1 = """
CREATE TABLE IF NOT EXISTS audit_l1_interaction (
    id                      BIGSERIAL       PRIMARY KEY,
    event_id                TEXT            NOT NULL UNIQUE,

    -- Hash chain (DORA-style integrity protection, see governance/integrity.py)
    prev_hash               TEXT,
    entry_hash              TEXT            NOT NULL,

    -- Correlation
    session_id              TEXT            NOT NULL,
    workflow_execution_id   TEXT            NOT NULL,
    event_type              TEXT            NOT NULL,

    -- Interaction metadata — GDPR Art. 25 data minimization: no raw content
    user_id_pseudo          TEXT,
    request_type            TEXT,
    message_length          INTEGER,
    detected_intent         TEXT,
    target_agent             TEXT,
    pii_detected             BOOLEAN         DEFAULT FALSE,
    pii_entity_types         TEXT[],
    risk_level               TEXT,
    outcome                  TEXT,

    created_at               TIMESTAMPTZ     NOT NULL DEFAULT now()
);
"""

_DDL_L2 = """
CREATE TABLE IF NOT EXISTS audit_l2_execution (
    id                      BIGSERIAL       PRIMARY KEY,
    event_id                TEXT            NOT NULL UNIQUE,

    prev_hash               TEXT,
    entry_hash              TEXT            NOT NULL,

    session_id              TEXT            NOT NULL,
    workflow_execution_id   TEXT            NOT NULL,
    event_type              TEXT            NOT NULL,

    -- Execution trace — GDPR Art. 22 explainability of automated decisions
    agent_id                 TEXT,
    nodes_visited             TEXT[],
    rag_used                  BOOLEAN,
    rag_documents_count       INTEGER,
    confidence_score          DOUBLE PRECISION,
    processing_duration_ms    INTEGER,
    model_info                 TEXT,
    judge_score                 DOUBLE PRECISION,
    hitl_triggered               BOOLEAN,
    execution_status             TEXT,
    error_message                 TEXT,

    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_DDL_L3 = """
CREATE TABLE IF NOT EXISTS audit_l3_governance (
    id                      BIGSERIAL       PRIMARY KEY,
    event_id                TEXT            NOT NULL UNIQUE,

    prev_hash               TEXT,
    entry_hash              TEXT            NOT NULL,

    session_id              TEXT            NOT NULL,
    workflow_execution_id   TEXT            NOT NULL,
    event_type              TEXT            NOT NULL,

    -- Governance / escalation trace — GDPR Art. 5(2) accountability
    risk_level                TEXT,
    escalation_reason           TEXT,
    hitl_required                 BOOLEAN,
    hitl_request_id                TEXT,
    human_decision                   TEXT,
    human_approver                     TEXT,
    rejection_reason                     TEXT,
    override_reason                        TEXT,
    judge_result                             JSONB,
    policy_decision                            TEXT,
    governance_action                            TEXT,

    created_at                                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_DDL_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_l1_session    ON audit_l1_interaction (session_id);
CREATE INDEX IF NOT EXISTS idx_l1_workflow   ON audit_l1_interaction (workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_l1_time       ON audit_l1_interaction (created_at);
CREATE INDEX IF NOT EXISTS idx_l1_risk       ON audit_l1_interaction (risk_level);

CREATE INDEX IF NOT EXISTS idx_l2_session    ON audit_l2_execution (session_id);
CREATE INDEX IF NOT EXISTS idx_l2_workflow   ON audit_l2_execution (workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_l2_event_type ON audit_l2_execution (event_type);
CREATE INDEX IF NOT EXISTS idx_l2_time       ON audit_l2_execution (created_at);

CREATE INDEX IF NOT EXISTS idx_l3_session    ON audit_l3_governance (session_id);
CREATE INDEX IF NOT EXISTS idx_l3_workflow   ON audit_l3_governance (workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_l3_event_type ON audit_l3_governance (event_type);
CREATE INDEX IF NOT EXISTS idx_l3_risk       ON audit_l3_governance (risk_level);
CREATE INDEX IF NOT EXISTS idx_l3_time       ON audit_l3_governance (created_at);
"""

# ── Append-only enforcement via Row-Level Security ──────────────────────────
# Kept from the original schema.sql design: FORCE ROW LEVEL SECURITY applies
# even to superusers (unlike plain REVOKE UPDATE/DELETE), and with no
# UPDATE/DELETE/TRUNCATE policy defined, those operations are denied for
# everyone. This is what makes the hash chain meaningful — the DB itself
# refuses to let the chain be edited after the fact, not just the app code.
_DDL_RLS = """
ALTER TABLE audit_l1_interaction ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_l2_execution   ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_l3_governance  ENABLE ROW LEVEL SECURITY;

ALTER TABLE audit_l1_interaction FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_l2_execution   FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_l3_governance  FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS allow_insert_l1 ON audit_l1_interaction;
DROP POLICY IF EXISTS allow_insert_l2 ON audit_l2_execution;
DROP POLICY IF EXISTS allow_insert_l3 ON audit_l3_governance;
DROP POLICY IF EXISTS allow_select_l1 ON audit_l1_interaction;
DROP POLICY IF EXISTS allow_select_l2 ON audit_l2_execution;
DROP POLICY IF EXISTS allow_select_l3 ON audit_l3_governance;

CREATE POLICY allow_insert_l1 ON audit_l1_interaction FOR INSERT WITH CHECK (true);
CREATE POLICY allow_insert_l2 ON audit_l2_execution   FOR INSERT WITH CHECK (true);
CREATE POLICY allow_insert_l3 ON audit_l3_governance  FOR INSERT WITH CHECK (true);

CREATE POLICY allow_select_l1 ON audit_l1_interaction FOR SELECT USING (true);
CREATE POLICY allow_select_l2 ON audit_l2_execution   FOR SELECT USING (true);
CREATE POLICY allow_select_l3 ON audit_l3_governance  FOR SELECT USING (true);

-- No UPDATE/DELETE/TRUNCATE policy => denied for ALL roles, including the
-- table owner, once FORCE ROW LEVEL SECURITY is set.
--
-- IMPORTANT, TESTED CAVEAT: FORCE ROW LEVEL SECURITY affects the table
-- OWNER (when the owner is not itself a superuser / BYPASSRLS role); it
-- does NOT and cannot affect a genuine Postgres superuser, who bypasses
-- row security unconditionally by design. RLS + REVOKE below stop the
-- application role (and any ordinary owner role) from ever issuing a
-- successful UPDATE/DELETE. They cannot stop a DBA connecting as a
-- superuser. That residual risk is exactly why governance/integrity.py's
-- hash chain exists: it doesn't prevent a superuser from editing a row,
-- it guarantees such an edit is *detectable* on the next verification run,
-- regardless of which role made the change.
"""


def _apply_privileges(cur, app_user: str) -> None:
    """Defense-in-depth on top of RLS: explicitly strip UPDATE/DELETE/
    TRUNCATE from the application role at the grant level too, and leave
    it only INSERT + SELECT. Belt-and-suspenders with the RLS policies
    above — two independent mechanisms have to both be bypassed (or a
    literal superuser session used) for a row to be altered undetected
    pre-hash-chain-verification."""
    ident = psycopg2.sql.Identifier(app_user)
    for table in TABLE_NAMES.values():
        table_ident = psycopg2.sql.Identifier(table)
        cur.execute(
            psycopg2.sql.SQL("REVOKE ALL ON {table} FROM {user};").format(
                table=table_ident, user=ident
            )
        )
        cur.execute(
            psycopg2.sql.SQL("GRANT SELECT, INSERT ON {table} TO {user};").format(
                table=table_ident, user=ident
            )
        )
        cur.execute(
            psycopg2.sql.SQL(
                "GRANT USAGE, SELECT ON SEQUENCE {seq} TO {user};"
            ).format(seq=psycopg2.sql.Identifier(f"{table}_id_seq"), user=ident)
        )

_DDL_COMMENTS = """
COMMENT ON TABLE audit_l1_interaction IS
    'L1 Interaction: what interaction happened. Metadata only, GDPR Art.25 data minimisation.';
COMMENT ON TABLE audit_l2_execution IS
    'L2 Execution: how the AI system processed the request. GDPR Art.22 explainability.';
COMMENT ON TABLE audit_l3_governance IS
    'L3 Governance: was the AI allowed to decide automatically, and what controls applied. GDPR Art.5(2).';
"""


def initialize_schema(drop_existing: bool = False, config: Optional[GovernanceDBConfig] = None) -> None:
    """Creates (or re-creates) the governance audit schema.

    drop_existing=True is destructive (wipes the hash-chained audit
    history) and is intended for local/dev/demo setup only — this is why
    it's not the default and the CLI requires an explicit flag.
    """
    cfg = config or get_db_config()
    logger.info("Initializing governance audit schema on %s", cfg.safe_repr())

    # Phase 1: tables, indexes, RLS — this is the mandatory, load-bearing
    # part of the schema. Committed in its own transaction so nothing that
    # happens afterwards can ever roll it back.
    with connection_scope(cfg) as conn:
        with conn.cursor() as cur:
            # No CREATE EXTENSION dependency (e.g. pgcrypto) on purpose: the
            # governance-DB role in production should not need CREATE-level
            # privileges. event_id is always supplied by Python
            # (models.new_event_id(), a uuid4) rather than generated
            # server-side, so no DB-side UUID function is required.
            if drop_existing:
                logger.warning("drop_existing=True: dropping existing audit tables")
                cur.execute(_DDL_DROP)
            cur.execute(_DDL_L1)
            cur.execute(_DDL_L2)
            cur.execute(_DDL_L3)
            cur.execute(_DDL_INDEXES)
            cur.execute(_DDL_RLS)
            cur.execute(_DDL_COMMENTS)

    logger.info("Governance audit schema ready (tables: %s)", ", ".join(TABLE_NAMES.values()))

    # Phase 2: explicit REVOKE/GRANT lockdown — optional hardening, run in
    # its OWN transaction/connection so that if it fails (e.g. because
    # init was run as the application role itself, which cannot
    # REVOKE/GRANT on itself) Phase 1's tables are completely unaffected.
    priv_conn = get_connection(cfg)
    try:
        with priv_conn.cursor() as cur:
            _apply_privileges(cur, cfg.user)
        priv_conn.commit()
        logger.info("Applied explicit REVOKE/GRANT lockdown for role '%s'", cfg.user)
    except psycopg2.errors.InsufficientPrivilege:
        priv_conn.rollback()
        logger.warning(
            "Skipped explicit privilege lockdown for role '%s' (insufficient "
            "privilege to REVOKE/GRANT on itself — this is expected when "
            "--init is run as the application role). RLS append-only "
            "protection is still fully active. For the additional REVOKE-"
            "level defense-in-depth, run --init once as a DB admin role.",
            cfg.user,
        )
    finally:
        priv_conn.close()


def schema_exists(config: Optional[GovernanceDBConfig] = None) -> bool:
    """Returns True if all three audit tables already exist."""
    cfg = config or get_db_config()
    query = """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%s)
    """
    with connection_scope(cfg) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (list(TABLE_NAMES.values()),))
            found = {row[0] for row in cur.fetchall()}
    return found == set(TABLE_NAMES.values())


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Governance audit schema management")
    parser.add_argument("--init", action="store_true", help="Create the audit tables if they don't exist")
    parser.add_argument("--drop-existing", action="store_true",
                         help="DESTRUCTIVE: drop and recreate the audit tables (dev/demo only)")
    parser.add_argument("--check", action="store_true", help="Check whether the schema already exists")
    args = parser.parse_args()

    if args.check:
        exists = schema_exists()
        print(f"Governance schema present: {exists}")
        return

    if args.init or args.drop_existing:
        initialize_schema(drop_existing=args.drop_existing)
        print("Governance audit schema initialized.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
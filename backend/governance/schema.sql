-- AWB Banking AI Governance Audit Schema
-- ============================================================
-- This file mirrors governance/audit_schema.py.
--
-- Normal initialization should be:
--
--     python -m governance.audit_schema --init
--
-- This SQL file is provided for DBA/manual migration workflows.
--
-- WARNING:
-- DROP TABLE statements are intentionally NOT included here.
-- Use:
--     python -m governance.audit_schema --init --drop-existing
-- only for local development/demo databases.
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_l1_interaction (
    id                    BIGSERIAL PRIMARY KEY,
    event_id              TEXT NOT NULL UNIQUE,
    prev_hash             TEXT,
    entry_hash            TEXT NOT NULL,

    session_id            TEXT NOT NULL,
    workflow_execution_id TEXT NOT NULL,
    event_type            TEXT NOT NULL,

    user_id_pseudo        TEXT,
    request_type          TEXT,
    message_length        INTEGER,
    detected_intent       TEXT,
    target_agent          TEXT,
    pii_detected          BOOLEAN DEFAULT FALSE,
    pii_entity_types      TEXT[],
    risk_level            TEXT,
    outcome               TEXT,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_l2_execution (
    id                       BIGSERIAL PRIMARY KEY,
    event_id                 TEXT NOT NULL UNIQUE,
    prev_hash                TEXT,
    entry_hash               TEXT NOT NULL,

    session_id               TEXT NOT NULL,
    workflow_execution_id    TEXT NOT NULL,
    event_type               TEXT NOT NULL,

    agent_id                 TEXT,
    nodes_visited            TEXT[],
    rag_used                BOOLEAN,
    rag_documents_count     INTEGER,
    confidence_score        DOUBLE PRECISION,
    processing_duration_ms  INTEGER,
    model_info              TEXT,
    judge_score             DOUBLE PRECISION,
    hitl_triggered           BOOLEAN,
    execution_status         TEXT,
    error_message            TEXT,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_l3_governance (
    id                    BIGSERIAL PRIMARY KEY,
    event_id              TEXT NOT NULL UNIQUE,
    prev_hash             TEXT,
    entry_hash            TEXT NOT NULL,

    session_id            TEXT NOT NULL,
    workflow_execution_id TEXT NOT NULL,
    event_type            TEXT NOT NULL,

    risk_level            TEXT,
    escalation_reason     TEXT,
    hitl_required         BOOLEAN,
    hitl_request_id       TEXT,
    human_decision        TEXT,
    human_approver        TEXT,
    rejection_reason      TEXT,
    override_reason       TEXT,
    judge_result          JSONB,
    policy_decision       TEXT,
    governance_action     TEXT,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_l1_session
    ON audit_l1_interaction (session_id);
CREATE INDEX IF NOT EXISTS idx_l1_workflow
    ON audit_l1_interaction (workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_l1_time
    ON audit_l1_interaction (created_at);
CREATE INDEX IF NOT EXISTS idx_l1_risk
    ON audit_l1_interaction (risk_level);

CREATE INDEX IF NOT EXISTS idx_l2_session
    ON audit_l2_execution (session_id);
CREATE INDEX IF NOT EXISTS idx_l2_workflow
    ON audit_l2_execution (workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_l2_event_type
    ON audit_l2_execution (event_type);
CREATE INDEX IF NOT EXISTS idx_l2_time
    ON audit_l2_execution (created_at);

CREATE INDEX IF NOT EXISTS idx_l3_session
    ON audit_l3_governance (session_id);
CREATE INDEX IF NOT EXISTS idx_l3_workflow
    ON audit_l3_governance (workflow_execution_id);
CREATE INDEX IF NOT EXISTS idx_l3_event_type
    ON audit_l3_governance (event_type);
CREATE INDEX IF NOT EXISTS idx_l3_risk
    ON audit_l3_governance (risk_level);
CREATE INDEX IF NOT EXISTS idx_l3_time
    ON audit_l3_governance (created_at);

-- Append-only protection.
ALTER TABLE audit_l1_interaction ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_l2_execution ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_l3_governance ENABLE ROW LEVEL SECURITY;

ALTER TABLE audit_l1_interaction FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_l2_execution FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_l3_governance FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS allow_insert_l1 ON audit_l1_interaction;
DROP POLICY IF EXISTS allow_insert_l2 ON audit_l2_execution;
DROP POLICY IF EXISTS allow_insert_l3 ON audit_l3_governance;
DROP POLICY IF EXISTS allow_select_l1 ON audit_l1_interaction;
DROP POLICY IF EXISTS allow_select_l2 ON audit_l2_execution;
DROP POLICY IF EXISTS allow_select_l3 ON audit_l3_governance;

CREATE POLICY allow_insert_l1
    ON audit_l1_interaction FOR INSERT WITH CHECK (true);
CREATE POLICY allow_insert_l2
    ON audit_l2_execution FOR INSERT WITH CHECK (true);
CREATE POLICY allow_insert_l3
    ON audit_l3_governance FOR INSERT WITH CHECK (true);

CREATE POLICY allow_select_l1
    ON audit_l1_interaction FOR SELECT USING (true);
CREATE POLICY allow_select_l2
    ON audit_l2_execution FOR SELECT USING (true);
CREATE POLICY allow_select_l3
    ON audit_l3_governance FOR SELECT USING (true);

COMMENT ON TABLE audit_l1_interaction IS
    'L1 Interaction: metadata about the interaction; no raw customer content.';
COMMENT ON TABLE audit_l2_execution IS
    'L2 Execution: trace of how the AI system processed the request.';
COMMENT ON TABLE audit_l3_governance IS
    'L3 Governance: risk, escalation, HITL and policy decisions.';

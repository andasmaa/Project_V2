# AWB Banking AI — Governance Layer Runbook

## 1. Purpose

This runbook explains how to install, initialize, run, test and evaluate the
governance layer integrated into the banking AI assistant.

The governance layer is responsible for:

- L1 interaction auditing
- L2 execution tracing
- L3 governance/HITL auditing
- PII-type detection without storing raw PII in audit records
- centralized risk classification
- cryptographic hash chaining
- audit-chain integrity verification
- PostgreSQL append-only protection
- governance metrics
- compliance dashboarding
- Banking77-based governance evaluation

It does **not** replace the existing LangGraph workflow, banking agents, RAG,
HITL mechanism, authentication or LLM.

---

## 2. Project layout

The files supplied by the governance integration are expected to live in
`backend/`.

```text
backend/
├── app.py
├── governance/
│   ├── __init__.py
│   ├── models.py
│   ├── audit_schema.py
│   ├── integrity.py
│   ├── risk_policy.py
│   ├── pii_protection.py
│   ├── audit_logger.py
│   ├── audit_service.py
│   ├── metrics.py
│   └── verify_chain.py
├── security/
│   ├── worm_audit.py
│   └── hitl_gate.py
├── agents/
│   └── audit_agent.py
├── workflow/
│   ├── state.py
│   └── langgraph_workflow.py
├── scripts/
│   ├── __init__.py
│   └── banking77_eval.py
├── tests/
│   └── governance/
│       ├── test_integrity.py
│       ├── test_pii_protection.py
│       ├── test_risk_policy.py
│       ├── test_audit_events.py
│       ├── test_hitl_governance.py
│       └── test_database.py
├── streamlit_app.py
├── schema.sql
├── requirements.txt
├── requirements-governance.txt
├── pytest.ini
└── .env
```

### Important note about the supplied ZIP

The ZIP used during development contains the governance test files, but they
were stored at the project root rather than under `tests/governance/`.

Move them to:

```text
backend/tests/governance/
```

so that the existing `pytest.ini`:

```ini
[pytest]
asyncio_mode = strict
testpaths = tests/governance
python_files = test_*.py
```

matches the actual project structure.

Do not modify the test logic merely to move the files.

---

## 3. Python environment

From `backend/`:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install the existing backend dependencies:

```bash
pip install -r requirements.txt
```

Then install the governance dependencies:

```bash
pip install -r requirements-governance.txt
```

The governance dependencies include PostgreSQL access, Streamlit and Plotly.

Presidio is optional. The current governance layer continues to work with its
regex detector if Presidio is not installed.

---

## 4. PostgreSQL database

The governance layer expects PostgreSQL.

Default development configuration:

```text
host     = localhost
port     = 5432
database = banking_audit
user     = audit_writer
```

Create the database and application role using an administrative PostgreSQL
account.

Example:

```sql
CREATE DATABASE banking_audit;

CREATE USER audit_writer WITH PASSWORD 'CHANGE_THIS_PASSWORD';

GRANT CONNECT ON DATABASE banking_audit TO audit_writer;
```

Connect to the database as an administrator before granting schema privileges:

```sql
\c banking_audit

GRANT USAGE ON SCHEMA public TO audit_writer;
```

The application role needs to be able to create/use the governance tables when
running the initialization command, or a DBA can run `schema.sql` first.

---

## 5. Environment configuration

Use the existing `.env` in `backend/`.

The governance variables are:

```env
GOVERNANCE_DB_HOST=localhost
GOVERNANCE_DB_PORT=5432
GOVERNANCE_DB_NAME=banking_audit
GOVERNANCE_DB_USER=audit_writer
GOVERNANCE_DB_PASSWORD=YOUR_POSTGRES_PASSWORD
GOVERNANCE_DB_SSLMODE=prefer

GOVERNANCE_FAILURE_MODE=fail_open
GOVERNANCE_FAILURE_MODE_HIGH_RISK=fail_closed

GOVERNANCE_CONFIDENCE_THRESHOLD=0.60
GOVERNANCE_JUDGE_SCORE_THRESHOLD=6.0

GOVERNANCE_PRESIDIO_ENABLED=false
GOVERNANCE_PRESIDIO_LANGUAGE=fr
```

Never commit a real database password to GitHub.

For production, use the existing Vault integration where configured, or inject
the database secret through the deployment environment.

---

## 6. Initialize the governance database

From `backend/`:

```bash
python -m governance.audit_schema --init
```

Check that the schema exists:

```bash
python -m governance.audit_schema --check
```

Expected tables:

```text
audit_l1_interaction
audit_l2_execution
audit_l3_governance
```

### Destructive reset

For a local/demo database only:

```bash
python -m governance.audit_schema --init --drop-existing
```

This destroys the existing governance audit history.

Do not use `--drop-existing` on a database whose audit history must be preserved.

---

## 7. Run the backend

From `backend/`:

```bash
uvicorn app:app --reload
```

The application should expose the existing banking API and the governance
endpoints.

Important governance endpoints:

```text
GET /audit/logs
GET /governance/verify
GET /governance/metrics
GET /governance/trace/{session_id}
```

The governance metrics and trace endpoints use the existing supervisor-role
authorization.

---

## 8. Governance lifecycle

For a normal request the audit trail is intended to look like:

```text
CHAT_REQUEST
      ↓
MODERATION_RESULT
      ↓
ROUTING_DECISION
      ↓
RAG_RETRIEVAL
      ↓
AGENT_EXECUTION
      ↓
JUDGE_EVALUATION
      ↓
CHAT_RESPONSE
```

For a request requiring human review, the governance layer additionally records
the relevant L3 HITL events:

```text
...
JUDGE_EVALUATION
      ↓
HITL_REQUIRED
      ↓
HITL_DECISION
      ↓
CHAT_RESPONSE
```

The exact sequence can vary when moderation blocks a request or when a workflow
branch legitimately terminates early.

---

## 9. L1 / L2 / L3 responsibilities

### L1 — Interaction

Records metadata about what happened:

- session identifier
- workflow execution identifier
- event type
- pseudonymous user identifier
- message length
- detected intent
- target agent
- PII type metadata
- risk level
- outcome

Raw customer message content is not stored in the governance tables.

### L2 — Execution

Records how the AI system processed the request:

- agent
- LangGraph nodes visited
- RAG usage
- number of retrieved documents
- confidence
- processing duration
- model information
- Judge score
- HITL trigger
- execution status

### L3 — Governance

Records control decisions:

- risk level
- escalation reason
- HITL requirement
- HITL request identifier
- human decision
- human approver
- rejection/override reason
- Judge result
- policy decision
- governance action

---

## 10. Hash-chain integrity

Every audit tier maintains its own append-only cryptographic chain.

Conceptually:

```text
GENESIS
   ↓
hash(event 1)
   ↓
hash(event 2)
   ↓
hash(event 3)
   ↓
...
```

Each event stores:

```text
prev_hash
entry_hash
```

The entry hash is derived deterministically from the previous hash and the
event payload.

The verifier recomputes the chain instead of trusting a stored
`integrity=true` flag.

Run the verifier:

```bash
python -m governance.verify_chain
```

Or use:

```text
GET /governance/verify
```

A valid result means that the stored rows still correspond to their expected
hash chain.

A PostgreSQL superuser can still modify database rows by design. The purpose of
the hash chain is therefore **tamper evidence/detection**, while PostgreSQL
RLS and privileges provide an additional append-only control for the normal
application role.

---

## 11. Run the tests

After moving the test files into:

```text
tests/governance/
```

run:

```bash
pytest tests/governance/ -v
```

The suite covers:

- hash-chain creation and verification
- tamper detection
- PII detection
- risk-policy behavior
- audit-event generation
- HITL governance behavior
- PostgreSQL integration

Database tests may require:

```env
TEST_DB_SUPERUSER_DSN=postgresql://postgres:YOUR_PASSWORD@localhost:5432/banking_audit
```

Use a dedicated local/test database when possible.

---

## 12. Streamlit compliance dashboard

Run:

```bash
streamlit run streamlit_app.py
```

The dashboard displays:

- L1/L2/L3 event counts
- HITL status
- risk distribution
- escalated risk distribution
- lifecycle event counts
- hash-chain verification
- session-level governance traces

It intentionally does not display raw message content.

---

## 13. Banking77 evaluation

The Banking77 benchmark is used only as a public research dataset for
governance-layer evaluation.

It is **not AWB customer data**.

The evaluation does not claim that Banking77 provides ground truth for the
project's AWB risk policy. Instead it evaluates:

1. governance-layer robustness
2. policy self-consistency
3. PII detection using synthetic injected values
4. optional workflow trace completeness
5. hash-chain integrity after the evaluation

Run a fast governance-only evaluation:

```bash
python -m scripts.banking77_eval --samples 500
```

Run one category:

```bash
python -m scripts.banking77_eval \
    --category compromised_card \
    --samples 20
```

Run the full workflow on a small sample:

```bash
python -m scripts.banking77_eval \
    --samples 20 \
    --full-workflow
```

Full-workflow evaluation is slower because it invokes the actual banking
workflow.

Results are saved under:

```text
scripts/data/banking77_eval_results.json
```

The dataset is downloaded automatically if it is not already present.

---

## 14. PII evaluation

The Banking77 evaluator injects synthetic values such as:

```text
test.eval.user1@example.com
0612345678
MA64011519000001205000534921
```

These are intentionally fake evaluation values.

The evaluator measures:

```text
PII recall
false-positive rate on clean samples
```

This is different from claiming that the dataset itself contains an AWB PII
ground truth.

---

## 15. Governance failure modes

Two failure modes are supported:

```text
fail_open
fail_closed
```

The general behavior is configurable through:

```env
GOVERNANCE_FAILURE_MODE=fail_open
```

High/critical-risk operations can use a stricter setting:

```env
GOVERNANCE_FAILURE_MODE_HIGH_RISK=fail_closed
```

This allows the project to distinguish ordinary observability failures from
governance failures affecting sensitive operations.

---

## 16. What belongs to each teammate

### Banking AI / agent contribution

The existing banking AI side provides:

- LangGraph orchestration
- banking agents
- intent routing
- RAG
- Judge
- HITL mechanism
- authentication/security
- banking workflow

### Governance contribution

The governance side provides:

- L1/L2/L3 audit architecture
- risk policy
- PII-aware audit metadata
- PostgreSQL audit storage
- cryptographic hash chains
- integrity verification
- governance metrics
- compliance dashboard
- governance evaluation using Banking77

The governance layer observes the existing workflow instead of replacing it.

---

## 17. Recommended demonstration for the PFE defense

Use one ordinary request and one sensitive request.

### Demonstration A — ordinary request

Send a normal banking information question.

Show:

```text
CHAT_REQUEST
→ MODERATION_RESULT
→ ROUTING_DECISION
→ RAG_RETRIEVAL
→ AGENT_EXECUTION
→ JUDGE_EVALUATION
→ CHAT_RESPONSE
```

Then open the governance trace.

### Demonstration B — sensitive request

Send a fraud/opposition-related request.

Show:

```text
risk = CRITICAL
HITL required = true
```

Then show the corresponding HITL request and governance event.

Finally run:

```text
/governance/verify
```

and demonstrate that the audit chain verifies successfully.

---

## 18. Important security notes

Do not:

- commit `.env`
- put real customer messages into audit logs
- put API keys into the dashboard
- call Banking77 customer data
- describe Banking77 as AWB data
- claim the risk policy is externally validated by Banking77
- claim a hash chain prevents a database administrator from editing data

The defensible claim is:

> The governance layer provides structured, privacy-aware, tamper-evident
> auditability for the banking AI workflow, with explicit risk and HITL
> governance records and automated integrity verification.

---

## 19. Final validation checklist

Before the PFE demonstration:

```text
[ ] PostgreSQL is running
[ ] banking_audit database exists
[ ] governance tables exist
[ ] .env is configured
[ ] backend starts
[ ] ordinary /chat request works
[ ] sensitive /chat request creates HITL
[ ] /governance/verify works
[ ] /governance/metrics works
[ ] /governance/trace/{session_id} works
[ ] pytest tests pass
[ ] Streamlit dashboard opens
[ ] Banking77 evaluation runs
[ ] evaluation JSON is generated
[ ] no secrets are committed
```

---

## 20. Quick command sequence

From `backend/`:

```bash
# 1. Environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# 2. Dependencies
pip install -r requirements.txt
pip install -r requirements-governance.txt

# 3. Database
python -m governance.audit_schema --init
python -m governance.audit_schema --check

# 4. Tests
pytest tests/governance/ -v

# 5. Backend
uvicorn app:app --reload

# 6. Dashboard (second terminal)
streamlit run streamlit_app.py

# 7. Governance evaluation (third terminal)
python -m scripts.banking77_eval --samples 500

# 8. Optional full workflow evaluation
python -m scripts.banking77_eval --samples 20 --full-workflow

# 9. Integrity verification
python -m governance.verify_chain
```

This is the complete local run sequence.

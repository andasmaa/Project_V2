# security/worm_audit.py
"""
Compatibility wrapper around the governance audit layer.

WHY THIS FILE LOOKS THE WAY IT DOES
------------------------------------
The original WormAudit wrote JSON-line entries to a local file
(audit_logs.json) and its verify_integrity() was a stub that
unconditionally returned True — it never actually checked anything.

This file keeps every existing call working, unchanged:

    worm_audit.write({...})
    worm_audit.get_recent_logs(limit)
    worm_audit.get_all_logs()
    worm_audit.get_stats()
    worm_audit.verify_integrity()          # now REAL, not a stub

...but internally:

  - .write() still writes the legacy JSON file (so get_recent_logs() /
    get_all_logs() / get_stats(), and any endpoint reading them such as
    GET /audit/logs, keep working exactly as before) AND ALSO forwards a
    best-effort event into the governance Postgres audit trail
    (governance.audit_service), so there is ONE durable, hash-chained
    source of truth rather than two audit systems running in parallel.

  - .verify_integrity() delegates to the real cryptographic hash-chain
    verifier (governance.verify_chain / governance.integrity) instead of
    unconditionally returning True.

HONEST LIMITATION, STATED EXPLICITLY: calls to .write({...}) carry a
free-form dict with no session_id / workflow_execution_id — the original
API never had these fields. Events bridged this way are recorded as
best-effort L2 "LEGACY_WORM_WRITE" execution events (nothing is silently
dropped), but they cannot be linked into a specific request's L1/L2/L3
chain-of-custody the way a properly instrumented workflow node can be.
Full traceability comes from workflow/langgraph_workflow.py calling
governance.audit_service directly with real session/workflow IDs at each
node — this wrapper's job is backward compatibility, not an upgrade of
the old call sites' fidelity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from governance.audit_service import AuditService
from governance.models import EventType, GovernanceFailureMode, Tier
from governance.verify_chain import verify_tier

logger = logging.getLogger("security.worm_audit")


class WormAudit:
    """Drop-in replacement for the original WormAudit. Same constructor
    signature, same public method names and return types for every
    method that existed before. verify_integrity() keeps returning a
    plain bool for backward compatibility (now a real one, not a stub);
    verify_integrity_report() is new and returns full per-tier detail."""

    def __init__(
        self,
        log_file: str = "audit_logs.json",
        audit_service: Optional[AuditService] = None,
    ):
        self.log_file = log_file
        self._init_log_file()

        # A governance-write failure must NEVER break the legacy
        # .write() call — that would be a behavior change existing
        # callers don't expect from what used to be a plain file write.
        # FAIL_OPEN here is deliberate and scoped to this compatibility
        # shim only: workflow nodes that call AuditService directly (see
        # workflow/langgraph_workflow.py) use the configured
        # GOVERNANCE_FAILURE_MODE instead, since that IS the primary
        # audit path and high-risk operations there may need to fail
        # closed.
        self._audit_service = audit_service or AuditService(
            failure_mode=GovernanceFailureMode.FAIL_OPEN
        )

    # ------------------------------------------------------------------
    # Legacy file handling — behavior unchanged from the original file
    # ------------------------------------------------------------------

    def _init_log_file(self) -> None:
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            logger.info("Fichier d'audit créé: %s", self.log_file)

    def _legacy_write(self, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logs = []

        log_entry = {
            "id": hashlib.md5(
                f"{datetime.now().isoformat()}{data.get('action', '')}".encode()
            ).hexdigest()[:8],
            "timestamp": datetime.now().isoformat(),
            "level": data.get("level", "INFO"),
            "action": data.get("action", "UNKNOWN"),
            "entity_id": data.get("entity_id", "system"),
            "message": data.get("message", ""),
            "details": data.get("details", {}),
            "hash": hashlib.sha256(
                json.dumps(data, sort_keys=True, default=str).encode()
            ).hexdigest()[:16],
        }

        logs.append(log_entry)
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)

        return log_entry

    # ------------------------------------------------------------------
    # Public API — same names/signatures the rest of the app already
    # calls (workflow/langgraph_workflow.py, app.py)
    # ------------------------------------------------------------------

    def write(self, data: Dict[str, Any]) -> None:
        """Writes the legacy JSON file (unchanged) AND bridges a
        best-effort event into the governance Postgres audit trail."""
        log_entry: Optional[Dict[str, Any]] = None
        try:
            log_entry = self._legacy_write(data)
        except Exception as exc:
            logger.error("Legacy audit file write failed: %s", exc)

        self._bridge_to_governance(data, log_entry)

    def _bridge_to_governance(
        self, data: Dict[str, Any], log_entry: Optional[Dict[str, Any]]
    ) -> None:
        """Best-effort L2 event for a legacy, unstructured .write() call.
        Never raises past this method — a governance failure here must
        not affect the caller (see class docstring: this is a
        compatibility shim, not the primary audit path)."""
        try:
            action = str(data.get("action", "UNKNOWN"))
            level = str(data.get("level", "INFO")).upper()
            details = data.get("details")
            message = data.get("message")

            error_message: Optional[str] = None
            if level == "ERROR":
                if isinstance(details, dict) and details.get("error"):
                    error_message = str(details["error"])
                elif message:
                    error_message = str(message)
                if error_message:
                    error_message = error_message[:500]

            self._audit_service.log_execution(
                session_id=str(data.get("entity_id") or "legacy_unknown"),
                workflow_execution_id=(log_entry or {}).get("id", "legacy_unknown"),
                event_type=EventType.AGENT_EXECUTION,
                agent_id="LEGACY_WORM_WRITE",
                execution_status="error" if level == "ERROR" else "success",
                error_message=error_message,
                model_info=f"legacy_action={action}",
            )
        except Exception as exc:
            logger.debug("Governance bridge for legacy write() skipped: %s", exc)

    def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Récupère les derniers logs (unchanged: reads the legacy
        JSON file, exactly as before)."""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8") as f:
                    logs = json.load(f)
                return logs[-limit:] if logs else []
        except Exception as exc:
            logger.error("Erreur lecture audit: %s", exc)
        return []

    def get_all_logs(self) -> List[Dict[str, Any]]:
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def get_stats(self) -> Dict[str, Any]:
        logs = self.get_recent_logs(1000)
        if not logs:
            return {"total": 0, "by_action": {}, "by_level": {}}

        by_action: Dict[str, int] = {}
        by_level: Dict[str, int] = {}
        for log in logs:
            action = log.get("action", "UNKNOWN")
            level = log.get("level", "INFO")
            by_action[action] = by_action.get(action, 0) + 1
            by_level[level] = by_level.get(level, 0) + 1

        return {"total": len(logs), "by_action": by_action, "by_level": by_level}

    # ------------------------------------------------------------------
    # Integrity — the real replacement for the old `return True` stub
    # ------------------------------------------------------------------

    def verify_integrity(self) -> bool:
        """Backward-compatible boolean API: True only if the ENTIRE
        hash-chained audit trail (L1 + L2 + L3) verifies cleanly. Unlike
        the original stub, this actually recomputes and checks every
        row. On a verification/connection failure this returns False,
        not True — a check that could not run is not a verified-valid
        chain, and silently trusting a bare `return True` is exactly the
        bug this file replaces."""
        try:
            report = self.verify_integrity_report()
            return bool(report.get("all_valid"))
        except Exception as exc:
            logger.error("verify_integrity() could not complete: %s", exc)
            return False

    def verify_integrity_report(self) -> Dict[str, Any]:
        """New method: full per-tier detail (which row broke, at which
        tier, and why) instead of a single opaque boolean. Used by the
        governance dashboard / a /governance/verify endpoint that needs
        to explain a failure rather than just flag one."""
        tiers: Dict[str, Any] = {}
        all_valid = True

        for tier in (Tier.L1, Tier.L2, Tier.L3):
            report = verify_tier(tier)
            tiers[tier.value] = {
                "chain_valid": report.chain_valid,
                "total_rows": report.total_rows,
                "ok_rows": report.ok_rows,
                "elapsed_ms": report.elapsed_ms,
                "tampered": [
                    {
                        "row_id": t.row_id,
                        "event_id": t.entry_id,
                        "detail": t.detail,
                    }
                    for t in report.tampered
                ],
                "first_broken_event": (
                    {
                        "row_id": report.first_broken_event.row_id,
                        "event_id": report.first_broken_event.entry_id,
                        "detail": report.first_broken_event.detail,
                    }
                    if report.first_broken_event
                    else None
                ),
            }
            if not report.chain_valid:
                all_valid = False

        return {"all_valid": all_valid, "tiers": tiers}
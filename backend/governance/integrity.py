"""
governance/integrity.py

Tamper-evident cryptographic hash chain for governance audit events.

Each audit row contains:

    prev_hash
    entry_hash

The first row has no previous hash.

For every following row:

    entry_hash =
        SHA256(canonical_event_data + prev_hash)

This makes modifications, deletions, and reordering detectable.

IMPORTANT:
This does not make the database absolutely immutable.
PostgreSQL permissions/RLS provide append-only protection,
while this hash chain makes unauthorized modifications detectable.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


GENESIS_HASH = "0" * 64


def normalize_timestamp(value: Any) -> Optional[str]:
    """Datetime -> UTC ISO-8601 string, independent of the DB session's
    timezone setting. Must be applied identically at write time (before
    hashing a freshly-built event) and at verify time (before hashing a
    row fetched back from Postgres) — psycopg2 returns TIMESTAMPTZ values
    as datetimes in the session's TimeZone setting, and two datetimes
    representing the same instant but different UTC offsets stringify
    differently via str(), which would otherwise make the hash
    irreproducible if the session timezone ever changes (e.g. a
    connection pooler or a server config change)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            from datetime import timezone as _tz
            value = value.replace(tzinfo=_tz.utc)
        from datetime import timezone as _tz
        return value.astimezone(_tz.utc).isoformat()
    return str(value)


def canonical_json(data: Dict[str, Any]) -> str:
    """
    Convert event data into deterministic JSON.

    Deterministic serialization is essential:
    the exact same data must always produce the same hash.
    """

    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def compute_entry_hash(
    event_data: Dict[str, Any],
    previous_hash: Optional[str],
) -> str:
    """
    Compute the SHA-256 hash for one audit event.

    The previous hash becomes part of the current hash,
    creating the chain.
    """

    prev = previous_hash or GENESIS_HASH

    payload = {
        "event": event_data,
        "prev_hash": prev,
    }

    serialized = canonical_json(payload)

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def build_hash_payload(
    event_data: Dict[str, Any],
    previous_hash: Optional[str],
) -> Dict[str, Any]:
    """
    Return the complete hash-chain payload.
    """

    prev = previous_hash or GENESIS_HASH

    entry_hash = compute_entry_hash(
        event_data=event_data,
        previous_hash=prev,
    )

    return {
        "prev_hash": prev,
        "entry_hash": entry_hash,
    }


def verify_entry(
    event_data: Dict[str, Any],
    stored_entry_hash: str,
    stored_previous_hash: Optional[str],
) -> bool:
    """
    Verify a single audit entry against its stored hash.
    """

    expected_hash = compute_entry_hash(
        event_data=event_data,
        previous_hash=stored_previous_hash,
    )

    return expected_hash == stored_entry_hash


@dataclass
class ChainState:
    """
    Keeps track of the latest hash while writing events.
    """

    last_hash: str = GENESIS_HASH

    def next_hash(
        self,
        event_data: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Generate the next prev_hash / entry_hash pair
        and advance the chain state.
        """

        result = build_hash_payload(
            event_data=event_data,
            previous_hash=self.last_hash,
        )

        self.last_hash = result["entry_hash"]

        return result


def normalize_db_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove database-only fields before recomputing the hash.

    The database primary key 'id' is deliberately excluded because
    it is not part of the logical audit event.
    """

    excluded = {
        "id",
        "prev_hash",
        "entry_hash",
    }

    normalized = {
        key: value
        for key, value in row.items()
        if key not in excluded
    }

    if "created_at" in normalized:
        normalized["created_at"] = normalize_timestamp(normalized["created_at"])

    return normalized


def verify_rows(rows: list[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify an ordered list of database audit rows.

    Expected input:
        rows sorted by chronological insertion order.

    Returns a structured verification result.
    """

    total = len(rows)
    valid = 0
    tampered = []

    previous_hash = GENESIS_HASH

    for row in rows:
        row_id = row.get("id")
        event_id = row.get("event_id")

        stored_previous_hash = row.get("prev_hash")
        stored_entry_hash = row.get("entry_hash")

        # Check chain link.
        if stored_previous_hash != previous_hash:
            tampered.append(
                {
                    "row_id": row_id,
                    "event_id": event_id,
                    "detail": "previous hash mismatch",
                }
            )

        event_data = normalize_db_row(row)

        expected_hash = compute_entry_hash(
            event_data=event_data,
            previous_hash=stored_previous_hash,
        )

        if expected_hash != stored_entry_hash:
            tampered.append(
                {
                    "row_id": row_id,
                    "event_id": event_id,
                    "detail": "entry hash mismatch",
                }
            )
        else:
            valid += 1

        previous_hash = stored_entry_hash or ""

    return {
        "chain_valid": len(tampered) == 0,
        "total_rows": total,
        "ok_rows": valid,
        "tampered": tampered,
        "first_broken_event": tampered[0] if tampered else None,
    }


def verify_all() -> Dict[str, Any]:
    """
    Convenience wrapper used by the compliance dashboard
    (streamlit_app.py): verifies all three tiers (L1/L2/L3) in one call
    and returns a combined report with a single overall `all_valid` flag
    plus each tier's full per-row detail, keyed by tier name.

    Imports verify_tier from governance.verify_chain LAZILY (inside the
    function body, not at module level) because verify_chain.py itself
    imports from THIS module (verify_rows) -- a module-level import here
    would create a circular import. By the time verify_all() is actually
    called, both modules have already finished loading, so the lazy
    import is safe.
    """
    from governance.models import Tier
    from governance.verify_chain import verify_tier

    tiers: Dict[str, Any] = {}
    all_valid = True

    for tier in (Tier.L1, Tier.L2, Tier.L3):
        report = verify_tier(tier)
        tiers[tier.value] = report.to_dict()
        if not report.chain_valid:
            all_valid = False

    return {"all_valid": all_valid, "tiers": tiers}
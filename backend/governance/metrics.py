from __future__ import annotations

from typing import Any, Dict, Optional

from governance.audit_schema import (
    TABLE_NAMES,
    GovernanceDBConfig,
    connection_scope,
)
from governance.models import Tier


class GovernanceMetrics:

    def __init__(
        self,
        config: Optional[GovernanceDBConfig] = None,
    ):
        self.config = config

    def summary(self) -> Dict[str, Any]:

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    f"SELECT COUNT(*) FROM {TABLE_NAMES[Tier.L1]}"
                )
                l1_count = cur.fetchone()[0]

                cur.execute(
                    f"SELECT COUNT(*) FROM {TABLE_NAMES[Tier.L2]}"
                )
                l2_count = cur.fetchone()[0]

                cur.execute(
                    f"SELECT COUNT(*) FROM {TABLE_NAMES[Tier.L3]}"
                )
                l3_count = cur.fetchone()[0]

                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {TABLE_NAMES[Tier.L3]}
                    WHERE hitl_required = TRUE
                    """
                )
                hitl_count = cur.fetchone()[0]

                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {TABLE_NAMES[Tier.L3]}
                    WHERE human_decision = 'approved'
                    """
                )
                approved_count = cur.fetchone()[0]

                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {TABLE_NAMES[Tier.L3]}
                    WHERE human_decision = 'rejected'
                    """
                )
                rejected_count = cur.fetchone()[0]

        return {
            "l1_events": l1_count,
            "l2_events": l2_count,
            "l3_events": l3_count,
            "hitl_required": hitl_count,
            "hitl_approved": approved_count,
            "hitl_rejected": rejected_count,
        }

    def risk_counts(self) -> Dict[str, int]:
        """Risk distribution across ALL interactions (L1, written for
        every request), not just the subset that got escalated to L3.
        L3 counts are also returned separately so a caller can see both
        "how risky was traffic overall" and "how much of that risk was
        actually escalated"."""

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    f"""
                    SELECT risk_level, COUNT(*)
                    FROM {TABLE_NAMES[Tier.L1]}
                    WHERE risk_level IS NOT NULL
                    GROUP BY risk_level
                    """
                )

                rows = cur.fetchall()

        return {
            risk: count
            for risk, count in rows
        }

    def escalated_risk_counts(self) -> Dict[str, int]:
        """Risk distribution restricted to interactions that actually
        produced an L3 governance event (i.e. were escalated/reviewed)."""

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                cur.execute(
                    f"""
                    SELECT risk_level, COUNT(*)
                    FROM {TABLE_NAMES[Tier.L3]}
                    WHERE risk_level IS NOT NULL
                    GROUP BY risk_level
                    """
                )

                rows = cur.fetchall()

        return {
            risk: count
            for risk, count in rows
        }

    def event_counts(self) -> Dict[str, int]:

        result: Dict[str, int] = {}

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                for table in TABLE_NAMES.values():

                    cur.execute(
                        f"""
                        SELECT event_type, COUNT(*)
                        FROM {table}
                        GROUP BY event_type
                        """
                    )

                    for event_type, count in cur.fetchall():
                        result[event_type] = (
                            result.get(event_type, 0) + count
                        )

        return result

    def session_trace(
        self,
        session_id: str,
    ) -> Dict[str, list]:

        result = {
            "L1": [],
            "L2": [],
            "L3": [],
        }

        with connection_scope(self.config) as conn:
            with conn.cursor() as cur:

                for tier, key in [
                    (Tier.L1, "L1"),
                    (Tier.L2, "L2"),
                    (Tier.L3, "L3"),
                ]:

                    table = TABLE_NAMES[tier]

                    cur.execute(
                        f"""
                        SELECT *
                        FROM {table}
                        WHERE session_id = %s
                        ORDER BY id ASC
                        """,
                        (session_id,),
                    )

                    columns = [
                        description[0]
                        for description in cur.description
                    ]

                    result[key] = [
                        dict(zip(columns, row))
                        for row in cur.fetchall()
                    ]

        return result
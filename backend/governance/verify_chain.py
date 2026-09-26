"""
governance/verify_chain.py

Command-line audit integrity verifier.

Usage:

    python -m governance.verify_chain

    python -m governance.verify_chain --tier L1

    python -m governance.verify_chain --tier L2

    python -m governance.verify_chain --tier L3
"""

from __future__ import annotations

import argparse
import time
from typing import Dict, List

from governance.audit_schema import (
    TABLE_NAMES,
    connection_scope,
)
from governance.integrity import verify_rows
from governance.models import (
    ChainVerificationReport,
    TamperedRow,
    Tier,
)


def load_rows(tier: Tier) -> List[Dict]:

    table = TABLE_NAMES[tier]

    with connection_scope() as conn:
        with conn.cursor() as cur:

            cur.execute(
                f"""
                SELECT *
                FROM {table}
                ORDER BY id ASC
                """
            )

            columns = [
                description[0]
                for description in cur.description
            ]

            return [
                dict(zip(columns, row))
                for row in cur.fetchall()
            ]


def verify_tier(tier: Tier) -> ChainVerificationReport:

    start = time.perf_counter()

    rows = load_rows(tier)

    result = verify_rows(rows)

    tampered = [
        TamperedRow(
            tier=tier,
            row_id=item["row_id"],
            entry_id=item.get("event_id"),
            timestamp=None,
            detail=item["detail"],
        )
        for item in result["tampered"]
    ]

    first = tampered[0] if tampered else None

    elapsed_ms = (
        time.perf_counter() - start
    ) * 1000

    return ChainVerificationReport(
        tier=tier.value,
        total_rows=result["total_rows"],
        ok_rows=result["ok_rows"],
        tampered=tampered,
        chain_valid=result["chain_valid"],
        elapsed_ms=elapsed_ms,
        first_broken_event=first,
    )


def print_report(report: ChainVerificationReport) -> None:

    print()
    print("=" * 60)
    print(f"Audit integrity verification — {report.tier}")
    print("=" * 60)

    print(f"Total rows : {report.total_rows}")
    print(f"Valid rows : {report.ok_rows}")
    print(f"Time       : {report.elapsed_ms:.2f} ms")

    if report.chain_valid:
        print()
        print("RESULT: VALID")
        print("No hash-chain integrity violation detected.")
        return

    print()
    print("RESULT: INVALID")
    print(
        f"Tampered/broken rows: {len(report.tampered)}"
    )

    for item in report.tampered[:20]:
        print(
            f"- row={item.row_id} "
            f"event={item.entry_id} "
            f"detail={item.detail}"
        )


def main() -> None:

    parser = argparse.ArgumentParser(
        description="Verify governance audit hash chains"
    )

    parser.add_argument(
        "--tier",
        choices=["L1", "L2", "L3", "ALL"],
        default="ALL",
    )

    args = parser.parse_args()

    if args.tier == "ALL":
        tiers = [
            Tier.L1,
            Tier.L2,
            Tier.L3,
        ]
    else:
        tiers = [
            Tier(args.tier)
        ]

    all_valid = True

    for tier in tiers:

        report = verify_tier(tier)

        print_report(report)

        if not report.chain_valid:
            all_valid = False

    print()

    if all_valid:
        print("GLOBAL RESULT: VALID")
    else:
        print("GLOBAL RESULT: INVALID")

        raise SystemExit(1)


if __name__ == "__main__":
    main()
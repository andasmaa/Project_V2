"""
scripts/banking77_eval.py
=========================

Evaluates the GOVERNANCE LAYER -- not a new banking LLM -- using the public
Banking77 intent-classification benchmark as varied banking-language input.

Banking77 is PUBLIC RESEARCH DATA. It is NOT Attijariwafa Bank customer data.
Nothing produced by this script should be described as AWB customer data.

What this evaluates:
1. Coverage/robustness of risk_policy + pii_protection.
2. Self-consistency of the project's own intent->risk policy.
3. PII detection on synthetic values injected by this script.
4. Optional full-workflow trace completeness.
5. Audit hash-chain integrity after evaluation.

It does NOT measure external "risk accuracy": Banking77 has no AWB risk labels.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from governance.pii_protection import detect_pii
from governance.risk_policy import assess_request


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
TRAIN_CSV = DATA_DIR / "banking77_train.csv"
RESULTS_JSON = DATA_DIR / "banking77_eval_results.json"

# Public raw CSV used by the original PolyAI-LDN task-specific-datasets repo.
BANKING77_SOURCE_URL = (
    "https://raw.githubusercontent.com/PolyAI-LDN/"
    "task-specific-datasets/master/banking_data/train.csv"
)

# Banking77 category -> simulated project intent.
# This is an explicit evaluation mapping, not a claim about AWB's production
# classifier.
BANKING77_TO_AWB_INTENT: Dict[str, str] = {
    "compromised_card": "fraud",
    "card_payment_not_recognised": "fraud",
    "cash_withdrawal_not_recognised": "fraud",
    "direct_debit_payment_not_recognised": "fraud",
    "transaction_charged_twice": "fraud",

    "lost_or_stolen_card": "opposition",
    "lost_or_stolen_phone": "opposition",
    "card_swallowed": "opposition",

    "terminate_account": "closure",

    "edit_personal_details": "rgpd",
    "why_verify_identity": "rgpd",
    "unable_to_verify_identity": "rgpd",
    "verify_my_identity": "rgpd",
    "verify_source_of_funds": "rgpd",
    "verify_top_up": "rgpd",

    "request_refund": "complaint",
    "Refund_not_showing_up": "complaint",
    "extra_charge_on_statement": "complaint",
    "card_payment_fee_charged": "complaint",
    "transfer_fee_charged": "complaint",
    "cash_withdrawal_charge": "complaint",
    "top_up_by_card_charge": "complaint",
    "exchange_charge": "complaint",
    "wrong_exchange_rate_for_cash_withdrawal": "complaint",
    "card_payment_wrong_exchange_rate": "complaint",

    "card_not_working": "incident",
    "contactless_not_working": "incident",
    "virtual_card_not_working": "incident",
    "atm_support": "incident",
    "pin_blocked": "incident",
    "declined_cash_withdrawal": "incident",
    "declined_transfer": "incident",
    "declined_card_payment": "incident",
    "failed_transfer": "incident",
    "top_up_failed": "incident",
    "passcode_forgotten": "incident",
    "beneficiary_not_allowed": "incident",
}

DEFAULT_AWB_INTENT = "info"

# These are the intents for which this project's own policy requires HITL.
# Derived from governance/risk_policy.py.
EXPECTED_ESCALATING_INTENTS = {
    "fraud",
    "opposition",
    "credit",
    "succession",
    "closure",
    "rgpd",
}

_FAKE_EMAILS = [
    "test.eval.user1@example.com",
    "eval.sample2@example.org",
    "banking77.eval3@example.net",
]
_FAKE_PHONES = ["0612345678", "0698765432", "0611223344"]
_FAKE_IBANS = [
    "MA64011519000001205000534921",
    "MA64011519000009876543210012",
]


@dataclass
class Banking77Sample:
    text: str
    category: str
    awb_intent: str
    injected_pii_types: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    total_samples: int = 0
    categories_seen: int = 0
    risk_distribution: Dict[str, int] = field(default_factory=dict)
    intent_coverage: Dict[str, int] = field(default_factory=dict)
    mapping_self_consistency_rate: float = 0.0
    pii_injected_count: int = 0
    pii_detected_of_injected: int = 0
    pii_recall: float = 0.0
    pii_clean_count: int = 0
    pii_false_positives: int = 0
    pii_false_positive_rate: float = 0.0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class TraceCompletenessResult:
    total_requests: int = 0
    complete_traces: int = 0
    completeness_rate: float = 0.0
    missing_event_examples: List[Dict[str, Any]] = field(default_factory=list)
    integrity_valid: Optional[bool] = None
    integrity_report: Dict[str, Any] = field(default_factory=dict)


EXPECTED_L2_SEQUENCE = [
    "MODERATION_RESULT",
    "ROUTING_DECISION",
    "RAG_RETRIEVAL",
    "AGENT_EXECUTION",
]


def map_to_awb_intent(category: str) -> str:
    return BANKING77_TO_AWB_INTENT.get(category, DEFAULT_AWB_INTENT)


def inject_synthetic_pii(
    text: str,
    rng: random.Random,
) -> tuple[str, List[str]]:
    injected_types: List[str] = []
    values: List[str] = []

    if rng.random() < 0.5:
        values.append(rng.choice(_FAKE_EMAILS))
        injected_types.append("EMAIL")

    if rng.random() < 0.5:
        values.append(rng.choice(_FAKE_PHONES))
        injected_types.append("PHONE")

    if not values:
        values.append(rng.choice(_FAKE_IBANS))
        injected_types.append("IBAN")

    return f"{text} ({' / '.join(values)})", injected_types


def _ensure_dataset() -> None:
    if TRAIN_CSV.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Banking77 train.csv not found at {TRAIN_CSV}")
    print("Downloading public Banking77 training CSV...")

    try:
        request = Request(
            BANKING77_SOURCE_URL,
            headers={"User-Agent": "banking-ai-governance-evaluation/1.0"},
        )
        with urlopen(request, timeout=60) as response:
            TRAIN_CSV.write_bytes(response.read())
    except Exception as exc:
        raise RuntimeError(
            "Could not download Banking77. Download the public training CSV "
            f"manually and place it at {TRAIN_CSV}. Source: "
            f"{BANKING77_SOURCE_URL}. Error: {exc}"
        ) from exc


def load_samples(
    total_samples: Optional[int] = None,
    category_filter: Optional[str] = None,
    pii_injection_rate: float = 0.2,
    seed: int = 42,
) -> List[Banking77Sample]:
    if not 0 <= pii_injection_rate <= 1:
        raise ValueError("pii_injection_rate must be between 0 and 1")

    _ensure_dataset()
    rng = random.Random(seed)

    with TRAIN_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if category_filter:
        rows = [row for row in rows if row.get("category") == category_filter]
        if not rows:
            raise ValueError(
                f"No Banking77 rows found for category={category_filter!r}"
            )

    rng.shuffle(rows)

    if total_samples is not None:
        if total_samples <= 0:
            raise ValueError("samples must be greater than zero")
        rows = rows[:total_samples]

    samples: List[Banking77Sample] = []

    for row in rows:
        text = row["text"]
        injected: List[str] = []

        if rng.random() < pii_injection_rate:
            text, injected = inject_synthetic_pii(text, rng)

        category = row["category"]

        samples.append(
            Banking77Sample(
                text=text,
                category=category,
                awb_intent=map_to_awb_intent(category),
                injected_pii_types=injected,
            )
        )

    return samples


def run_governance_only_eval(
    samples: List[Banking77Sample],
) -> EvalResult:
    result = EvalResult(total_samples=len(samples))

    risk_counts: Counter[str] = Counter()
    intent_counts: Counter[str] = Counter()
    categories = set()

    consistent = 0
    pii_injected = 0
    pii_detected = 0
    pii_clean = 0
    pii_false_positive = 0

    started = time.monotonic()

    for sample in samples:
        categories.add(sample.category)

        try:
            # 0.85 is deliberately fixed: this evaluation isolates the
            # intent -> risk policy rather than confidence behavior.
            risk = assess_request(
                intent=sample.awb_intent,
                confidence=0.85,
            )

            risk_counts[risk.risk_level.value] += 1
            intent_counts[sample.awb_intent] += 1

            expected_escalation = (
                sample.awb_intent in EXPECTED_ESCALATING_INTENTS
            )

            if risk.hitl_required == expected_escalation:
                consistent += 1

            pii_result = detect_pii(sample.text)

            if sample.injected_pii_types:
                pii_injected += 1

                detected_types = set(pii_result.entity_types)
                injected_types = set(sample.injected_pii_types)

                if pii_result.pii_detected and detected_types & injected_types:
                    pii_detected += 1
            else:
                pii_clean += 1
                if pii_result.pii_detected:
                    pii_false_positive += 1

        except Exception as exc:
            result.errors.append(
                f"{sample.category}: {type(exc).__name__}: {exc}"
            )

    result.categories_seen = len(categories)
    result.elapsed_seconds = round(time.monotonic() - started, 3)
    result.risk_distribution = dict(risk_counts)
    result.intent_coverage = dict(intent_counts)

    if samples:
        result.mapping_self_consistency_rate = round(
            consistent / len(samples),
            4,
        )

    result.pii_injected_count = pii_injected
    result.pii_detected_of_injected = pii_detected

    if pii_injected:
        result.pii_recall = round(
            pii_detected / pii_injected,
            4,
        )

    result.pii_clean_count = pii_clean
    result.pii_false_positives = pii_false_positive

    if pii_clean:
        result.pii_false_positive_rate = round(
            pii_false_positive / pii_clean,
            4,
        )

    return result


async def run_full_workflow_eval(
    samples: List[Banking77Sample],
) -> TraceCompletenessResult:
    from governance.audit_schema import connection_scope
    from governance.models import Tier
    from governance.verify_chain import verify_tier
    from workflow.langgraph_workflow import BankAgentWorkflow

    workflow = BankAgentWorkflow()
    result = TraceCompletenessResult(total_requests=len(samples))

    for sample in samples:
        session_id = f"banking77-eval-{uuid.uuid4()}"

        try:
            await workflow.process_message(
                sample.text,
                "chat_user",
                session_id,
            )
        except Exception as exc:
            result.missing_event_examples.append(
                {
                    "session_id": session_id,
                    "category": sample.category,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        with connection_scope() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_type
                    FROM audit_l2_execution
                    WHERE session_id = %s
                    ORDER BY id ASC
                    """,
                    (session_id,),
                )
                l2_events = [row[0] for row in cur.fetchall()]

        # Moderation can legitimately short-circuit the workflow.
        complete = (
            l2_events == ["MODERATION_RESULT"]
            or (
                "MODERATION_RESULT" in l2_events
                and all(event in l2_events for event in EXPECTED_L2_SEQUENCE)
            )
        )

        if complete:
            result.complete_traces += 1
        else:
            result.missing_event_examples.append(
                {
                    "session_id": session_id,
                    "category": sample.category,
                    "got_events": l2_events,
                }
            )

    if result.total_requests:
        result.completeness_rate = round(
            result.complete_traces / result.total_requests,
            4,
        )

    tiers_ok = True

    for tier in (Tier.L1, Tier.L2, Tier.L3):
        report = verify_tier(tier)
        result.integrity_report[tier.value] = {
            "chain_valid": report.chain_valid,
            "total_rows": report.total_rows,
        }

        if not report.chain_valid:
            tiers_ok = False

    result.integrity_valid = tiers_ok
    return result


def print_report(
    gov_result: EvalResult,
    trace_result: Optional[TraceCompletenessResult],
) -> None:
    print("\n" + "=" * 72)
    print("BANKING77 GOVERNANCE-LAYER EVALUATION")
    print("(public benchmark dataset -- NOT AWB customer data)")
    print("=" * 72)

    print(
        f"\nSamples evaluated: {gov_result.total_samples}"
        f" | categories seen: {gov_result.categories_seen}"
        f" | elapsed: {gov_result.elapsed_seconds}s"
    )

    if gov_result.errors:
        print(
            f"Errors during evaluation: {len(gov_result.errors)} "
            "(see JSON output)"
        )

    print("\n-- Risk distribution --")

    for level in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        count = gov_result.risk_distribution.get(level, 0)
        percentage = (
            100 * count / gov_result.total_samples
            if gov_result.total_samples
            else 0
        )
        print(f"  {level:10s} {count:5d} ({percentage:.1f}%)")

    print(
        "\n-- Mapping self-consistency: "
        f"{gov_result.mapping_self_consistency_rate * 100:.1f}% --"
    )
    print(
        "   This measures consistency with the project's own policy, "
        "not external risk ground truth."
    )

    print("\n-- Synthetic PII detection --")
    print(
        "   Recall: "
        f"{gov_result.pii_recall * 100:.1f}% "
        f"({gov_result.pii_detected_of_injected}/"
        f"{gov_result.pii_injected_count})"
    )
    print(
        "   False-positive rate: "
        f"{gov_result.pii_false_positive_rate * 100:.1f}% "
        f"({gov_result.pii_false_positives}/"
        f"{gov_result.pii_clean_count})"
    )

    if trace_result is not None:
        print("\n-- Full-workflow trace completeness --")
        print(
            f"   Complete traces: {trace_result.complete_traces}/"
            f"{trace_result.total_requests} "
            f"({trace_result.completeness_rate * 100:.1f}%)"
        )
        print(
            "   Audit-chain integrity: "
            + ("VALID" if trace_result.integrity_valid else "INVALID")
        )

    print("\n" + "=" * 72 + "\n")


def save_results(
    gov_result: EvalResult,
    trace_result: Optional[TraceCompletenessResult],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, Any] = {
        "governance_only": asdict(gov_result),
    }

    if trace_result is not None:
        payload["full_workflow"] = asdict(trace_result)

    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Results saved to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the governance layer using Banking77."
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=500,
        help="Number of Banking77 training samples to evaluate.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Evaluate only one Banking77 category.",
    )
    parser.add_argument(
        "--full-workflow",
        action="store_true",
        help="Also execute the real LangGraph workflow.",
    )
    parser.add_argument(
        "--pii-injection-rate",
        type=float,
        default=0.2,
        help="Fraction of samples receiving synthetic PII.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(RESULTS_JSON),
        help="Output JSON path.",
    )

    args = parser.parse_args()

    samples = load_samples(
        total_samples=args.samples,
        category_filter=args.category,
        pii_injection_rate=args.pii_injection_rate,
        seed=args.seed,
    )

    governance_result = run_governance_only_eval(samples)

    trace_result: Optional[TraceCompletenessResult] = None

    if args.full_workflow:
        # Keep workflow evaluation bounded because it invokes the actual
        # banking workflow. The governance-only evaluation still uses all
        # requested samples.
        workflow_samples = samples[: min(len(samples), 50)]
        trace_result = asyncio.run(
            run_full_workflow_eval(workflow_samples)
        )

    print_report(governance_result, trace_result)
    save_results(
        governance_result,
        trace_result,
        Path(args.output),
    )


if __name__ == "__main__":
    main()

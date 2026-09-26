"""
governance/pii_protection.py

Privacy-aware audit helper.

The banking application already contains a pseudonymization mechanism.
This module does NOT create a competing anonymization pipeline.

Its purpose is to:

1. reuse the existing pseudonymizer when available;
2. identify PII types for audit metadata;
3. never return raw PII in the audit metadata;
4. optionally use Presidio for enrichment.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable, Optional

from governance.models import PIIDetectionResult


# ---------------------------------------------------------------------------
# Lightweight detection
# ---------------------------------------------------------------------------

PATTERNS = {
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),

    "PHONE": re.compile(
        r"(?<!\d)(?:\+212|0)(?:[5-7]\d{8})(?!\d)"
    ),

    "IBAN": re.compile(
        r"\bMA\d{2}[A-Z0-9]{20,28}\b",
        re.IGNORECASE,
    ),

    "CIN": re.compile(
        r"\b[A-Z]{1,2}\d{5,8}\b",
        re.IGNORECASE,
    ),
}


def detect_pii_regex(text: str) -> PIIDetectionResult:
    """
    Detect PII types without returning the actual values.
    """

    if not text:
        return PIIDetectionResult(
            pii_detected=False,
            entity_types=[],
            detection_method="regex",
        )

    entity_types = []

    for entity_type, pattern in PATTERNS.items():
        if pattern.search(text):
            entity_types.append(entity_type)

    return PIIDetectionResult(
        pii_detected=bool(entity_types),
        entity_types=entity_types,
        detection_method="regex",
    )


# ---------------------------------------------------------------------------
# Optional Presidio enrichment
# ---------------------------------------------------------------------------

def detect_pii_presidio(
    text: str,
) -> Optional[PIIDetectionResult]:
    """
    Optional Presidio-based detection.

    If Presidio is not installed/configured, returns None instead
    of breaking the banking application.
    """

    try:
        from presidio_analyzer import AnalyzerEngine
    except ImportError:
        return None

    if not text:
        return PIIDetectionResult(
            pii_detected=False,
            entity_types=[],
            detection_method="presidio",
        )

    try:
        analyzer = AnalyzerEngine()

        results = analyzer.analyze(
            text=text,
            language=os.getenv("GOVERNANCE_PRESIDIO_LANGUAGE", "fr"),
        )

        entity_types = sorted(
            {
                result.entity_type
                for result in results
            }
        )

        return PIIDetectionResult(
            pii_detected=bool(entity_types),
            entity_types=entity_types,
            detection_method="presidio",
        )

    except Exception:
        return None


# ---------------------------------------------------------------------------
# Combined detector
# ---------------------------------------------------------------------------

def detect_pii(
    text: str,
    use_presidio: Optional[bool] = None,
) -> PIIDetectionResult:
    """
    Combine lightweight detection with optional Presidio metadata.

    use_presidio=None (the default) reads GOVERNANCE_PRESIDIO_ENABLED from
    the environment, so callers don't each have to know/duplicate that
    toggle — pass True/False explicitly only to override it for a
    specific call (e.g. tests).
    """

    regex_result = detect_pii_regex(text)

    if use_presidio is None:
        use_presidio = os.getenv("GOVERNANCE_PRESIDIO_ENABLED", "false").strip().lower() in ("1", "true", "yes")

    if not use_presidio:
        return regex_result

    presidio_result = detect_pii_presidio(text)

    if presidio_result is None:
        return regex_result

    entity_types = sorted(
        set(regex_result.entity_types)
        | set(presidio_result.entity_types)
    )

    return PIIDetectionResult(
        pii_detected=bool(entity_types),
        entity_types=entity_types,
        detection_method="regex+presidio",
    )


# ---------------------------------------------------------------------------
# Existing pseudonymizer adapter
# ---------------------------------------------------------------------------

def pseudonymize_with_existing(
    text: str,
    existing_pseudonymizer: Optional[Callable[[str], str]] = None,
) -> str:
    """
    Reuse the teammate's existing pseudonymization function.

    If a function is supplied, it is used directly.

    Otherwise the original text is returned unchanged.

    IMPORTANT:
    This fallback is intentional. It prevents this module from silently
    pretending that a string was pseudonymized when no pseudonymizer exists.

    Callers that persist audit data should use the teammate's actual
    pseudonymizer before storing identifiers/content.
    """

    if not text:
        return text

    if existing_pseudonymizer is None:
        return text

    return existing_pseudonymizer(text)
"""
tests/governance/test_pii_protection.py
==========================================
Covers spec item 17 "PII tests": emails, phone numbers, CIN, IBAN etc.
are detected as metadata but never stored/returned in raw form.

Pure unit tests -- no database needed, so no clean_db/superuser_conn
fixtures here.
"""

from __future__ import annotations

import os

import pytest

from governance.pii_protection import detect_pii, detect_pii_regex


class TestRegexDetection:
    def test_email_detected(self):
        result = detect_pii_regex("Contactez-moi a jean.dupont@example.com pour plus d'infos")
        assert result.pii_detected is True
        assert "EMAIL" in result.entity_types

    def test_moroccan_phone_detected(self):
        result = detect_pii_regex("Mon numero est 0612345678")
        assert result.pii_detected is True
        assert "PHONE" in result.entity_types

    def test_iban_detected(self):
        result = detect_pii_regex("IBAN: MA64011519000001205000534921")
        assert result.pii_detected is True
        assert "IBAN" in result.entity_types

    def test_cin_detected(self):
        # Moroccan national ID format: 1-2 letters + 5-7 digits
        result = detect_pii_regex("Mon CIN est BE123456")
        assert result.pii_detected is True
        assert "CIN" in result.entity_types

    def test_no_pii_in_clean_message(self):
        result = detect_pii_regex("Quel est le taux d'interet pour un credit immobilier ?")
        assert result.pii_detected is False
        assert result.entity_types == []

    def test_multiple_pii_types_all_detected(self):
        msg = "Je suis jean.dupont@example.com, tel 0612345678, IBAN MA64011519000001205000534921"
        result = detect_pii_regex(msg)
        assert result.pii_detected is True
        assert {"EMAIL", "PHONE", "IBAN"}.issubset(set(result.entity_types))


class TestDataMinimization:
    """The critical property: whatever detect_pii() returns must NEVER
    contain the raw matched text, only entity-type labels + a boolean."""

    def test_result_never_contains_raw_email(self):
        msg = "Ecrivez-moi a secret.person@example.com"
        result = detect_pii(msg)
        serialized = str(result.to_dict())
        assert "secret.person@example.com" not in serialized

    def test_result_never_contains_raw_iban(self):
        msg = "Virement vers MA64011519000001205000534921 stp"
        result = detect_pii(msg)
        serialized = str(result.to_dict())
        assert "MA64011519000001205000534921" not in serialized

    def test_to_dict_shape_is_metadata_only(self):
        result = detect_pii("test jean@example.com")
        d = result.to_dict()
        assert set(d.keys()) == {"pii_detected", "entity_types", "detection_method"}
        assert isinstance(d["entity_types"], list)
        assert all(isinstance(x, str) for x in d["entity_types"])


class TestPresidioToggle:
    """Presidio is optional; detect_pii() must degrade gracefully and
    predictably based on GOVERNANCE_PRESIDIO_ENABLED."""

    def test_disabled_by_default_uses_regex_only(self, monkeypatch):
        monkeypatch.delenv("GOVERNANCE_PRESIDIO_ENABLED", raising=False)
        result = detect_pii("jean@example.com")
        assert result.detection_method == "regex"

    def test_explicit_false_uses_regex_only(self):
        result = detect_pii("jean@example.com", use_presidio=False)
        assert result.detection_method == "regex"

    def test_env_flag_is_read_when_not_overridden(self, monkeypatch):
        monkeypatch.setenv("GOVERNANCE_PRESIDIO_ENABLED", "false")
        result = detect_pii("jean@example.com")
        assert result.detection_method == "regex"

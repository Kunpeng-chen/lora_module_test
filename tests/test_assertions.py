from __future__ import annotations

from lora_auto.libs.assertions import assert_contains, assert_payload_equal, assert_regex


def test_assert_contains_passes_when_expected_text_exists() -> None:
    result = assert_contains("OK\r\n", "OK")

    assert result.passed is True
    assert "contains" in result.message


def test_assert_contains_fails_when_expected_text_is_missing() -> None:
    result = assert_contains("ERROR\r\n", "OK")

    assert result.passed is False
    assert "expected" in result.message


def test_assert_regex_passes_when_pattern_matches() -> None:
    result = assert_regex("+VERSION=V1.2.4", r"\+VERSION=V\d+\.\d+\.\d+")

    assert result.passed is True


def test_assert_regex_fails_when_pattern_does_not_match() -> None:
    result = assert_regex("ERROR", r"\+VERSION")

    assert result.passed is False


def test_assert_payload_equal_uses_containment_for_mvp_noise_tolerance() -> None:
    result = assert_payload_equal("123456789", "noise:123456789\r\n")

    assert result.passed is True


def test_assert_payload_equal_fails_when_payload_is_missing() -> None:
    result = assert_payload_equal("123456789", "abcdef")

    assert result.passed is False

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from lora_auto.libs.formal_cases import FormalCaseError, load_formal_case_directory, validate_formal_cases


FORMAL_CASE_DIR = Path(__file__).resolve().parents[1] / "lora_auto" / "config" / "formal"


def test_loads_formal_case_samples_and_phase2_at_cases() -> None:
    cases = load_formal_case_directory(FORMAL_CASE_DIR)

    assert [case["id"] for case in cases if case["suite"] == "at"] == [
        f"AT-{index:03d}" for index in range(1, 21)
    ]
    assert {case["suite"] for case in cases} == {"main", "at", "error_at", "ship", "iter"}
    assert {"MAIN-001", "ERRAT-001", "SHIP-001", "ITER-001"}.issubset(
        {case["id"] for case in cases}
    )


def test_phase2_at_cases_include_command_expected_and_manual_ref() -> None:
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "at"]

    assert len(cases) == 20
    for case in cases:
        assert case["metadata"]["manual_ref"]
        assert case["metadata"]["manual_ref"] != "docs/manual/dx-lr31-900t22s-uart-application-guide.md"
        assert case["steps"]
        for step in case["steps"]:
            assert step["command"]
            assert step["expected"]
            assert step["expected"]["mode"] in {"contains", "contains_all", "regex", "exact"}


def test_phase4_error_at_cases_are_expanded_and_numbered() -> None:
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "error_at"]

    assert len(cases) == 57
    assert [case["id"] for case in cases] == [f"ERRAT-{index:03d}" for index in range(1, 58)]


def test_phase4_error_at_cases_use_expected_error_codes_and_post_check() -> None:
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "error_at"]

    for index, case in enumerate(cases, start=1):
        expected_error = "ERROR=104" if index <= 13 else "ERROR=105"
        assert case["automation_level"] == "auto"
        assert case["metadata"]["run_policy"] == "auto"
        assert case["metadata"]["destructive"] is False
        assert case["metadata"]["state_changing"] is False
        assert case["steps"][0]["action"] == "send_at"
        assert case["steps"][0]["expected"] == {"mode": "contains", "value": expected_error}
        assert case["steps"][1] == {
            "action": "post_check",
            "device": "A",
            "command": "AT",
            "expected": {"mode": "contains", "value": "OK"},
        }
        assert "EEROR" not in str(case)


def test_phase2_at_default_is_manual_confirm_and_destructive() -> None:
    cases = {case["id"]: case for case in load_formal_case_directory(FORMAL_CASE_DIR)}

    at_default = cases["AT-020"]
    assert at_default["steps"][0]["command"] == "AT+DEFAULT"
    assert at_default["automation_level"] == "semi_auto"
    assert at_default["metadata"]["destructive"] is True
    assert at_default["metadata"]["state_changing"] is True
    assert at_default["metadata"]["run_policy"] == "manual_confirm"


def test_phase2_at_reset_is_state_changing_manual_confirm() -> None:
    cases = {case["id"]: case for case in load_formal_case_directory(FORMAL_CASE_DIR)}

    at_reset = cases["AT-019"]
    assert at_reset["steps"][0]["command"] == "AT+RESET"
    assert at_reset["automation_level"] == "semi_auto"
    assert at_reset["metadata"]["destructive"] is False
    assert at_reset["metadata"]["state_changing"] is True
    assert at_reset["metadata"]["run_policy"] == "manual_confirm"


def test_missing_required_field_fails() -> None:
    case = deepcopy(load_formal_case_directory(FORMAL_CASE_DIR)[0])
    del case["priority"]

    with pytest.raises(FormalCaseError, match="missing required fields: priority"):
        validate_formal_cases([case])


def test_duplicate_case_id_fails() -> None:
    case = deepcopy(load_formal_case_directory(FORMAL_CASE_DIR)[0])

    with pytest.raises(FormalCaseError, match="duplicate formal case id: MAIN-001"):
        validate_formal_cases([case, deepcopy(case)])


def test_invalid_priority_fails() -> None:
    case = deepcopy(load_formal_case_directory(FORMAL_CASE_DIR)[0])
    case["priority"] = "P3"

    with pytest.raises(FormalCaseError, match="invalid priority"):
        validate_formal_cases([case])


def test_invalid_automation_level_fails() -> None:
    case = deepcopy(load_formal_case_directory(FORMAL_CASE_DIR)[0])
    case["automation_level"] = "robot"

    with pytest.raises(FormalCaseError, match="invalid automation_level"):
        validate_formal_cases([case])


def test_destructive_case_can_be_modelled_but_not_auto_run() -> None:
    case = deepcopy(load_formal_case_directory(FORMAL_CASE_DIR)[1])
    case["id"] = "AT-DESTRUCTIVE-SAMPLE"
    case["automation_level"] = "semi_auto"
    case["metadata"]["destructive"] = True
    case["metadata"]["state_changing"] = True
    case["metadata"]["run_policy"] = "manual_confirm"
    validate_formal_cases([case])

    case["metadata"]["run_policy"] = "auto"
    with pytest.raises(FormalCaseError, match="destructive and must not use run_policy 'auto'"):
        validate_formal_cases([case])

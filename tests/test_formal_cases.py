from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from lora_auto.libs.formal_cases import FormalCaseError, load_formal_case_directory, validate_formal_cases


FORMAL_CASE_DIR = Path(__file__).resolve().parents[1] / "lora_auto" / "config" / "formal"


def test_loads_phase1_formal_case_samples() -> None:
    cases = load_formal_case_directory(FORMAL_CASE_DIR)

    assert [case["id"] for case in cases] == [
        "MAIN-001",
        "AT-001",
        "ERRAT-001",
        "SHIP-001",
        "ITER-001",
    ]
    assert {case["suite"] for case in cases} == {"main", "at", "error_at", "ship", "iter"}


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

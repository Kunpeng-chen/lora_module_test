from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from lora_auto.libs.formal_cases import FormalCaseError, load_formal_case_directory, validate_formal_cases


FORMAL_CASE_DIR = Path(__file__).resolve().parents[1] / "lora_auto" / "config" / "formal"
TRANSFER_PAYLOAD = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def test_loads_formal_case_samples_and_phase2_at_cases() -> None:
    cases = load_formal_case_directory(FORMAL_CASE_DIR)

    assert [case["id"] for case in cases if case["suite"] == "at"] == [
        f"AT-{index:03d}" for index in range(1, 21)
    ]
    assert [case["id"] for case in cases if case["suite"] == "main"] == [
        f"MAIN-{index:03d}" for index in range(1, 7)
    ]
    assert {case["suite"] for case in cases} == {"main", "at", "error_at", "ship", "iter"}
    assert {"ERRAT-001", "SHIP-001", "ITER-001"}.issubset(
        {case["id"] for case in cases}
    )


def test_phase5_main_transfer_cases_cover_types_modes_and_roles() -> None:
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "main"]

    assert len(cases) == 6
    assert {case["feature"] for case in cases} == {
        "transparent_transfer",
        "fixed_transfer",
        "broadcast_transfer",
    }
    assert {case["metadata"]["work_mode"] for case in cases} == {"SLEEP1", "SLEEP2"}

    cases_by_id = {case["id"]: case for case in cases}
    assert cases_by_id["MAIN-001"]["feature"] == "transparent_transfer"
    assert cases_by_id["MAIN-002"]["feature"] == "transparent_transfer"
    assert cases_by_id["MAIN-003"]["feature"] == "fixed_transfer"
    assert cases_by_id["MAIN-004"]["feature"] == "fixed_transfer"
    assert cases_by_id["MAIN-005"]["feature"] == "broadcast_transfer"
    assert cases_by_id["MAIN-006"]["feature"] == "broadcast_transfer"
    assert cases_by_id["MAIN-005"]["devices"] == ["A", "B", "C"]
    assert cases_by_id["MAIN-006"]["devices"] == ["A", "B", "C"]


def test_phase5_main_transfer_cases_model_key_rounds_for_all_participants() -> None:
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "main"]

    for case in cases:
        configure_steps = [step for step in case["steps"] if step["action"] == "configure_transfer_round"]
        assert [step["key_mode"] for step in configure_steps] == ["no_key", "shared_key"]
        assert case["metadata"]["key_modes"] == ["no_key", "shared_key"]

        no_key_step, shared_key_step = configure_steps
        assert set(no_key_step["config"]) == set(case["devices"])
        assert set(shared_key_step["config"]) == set(case["devices"])
        assert all(device_config["key"] is None for device_config in no_key_step["config"].values())

        shared_keys = {device_config["key"] for device_config in shared_key_step["config"].values()}
        assert shared_keys == {shared_key_step["shared_key"]}


def test_phase5_all_transfer_payloads_use_alphabet_sequence() -> None:
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "main"]

    for case in cases:
        payload_steps = [step for step in case["steps"] if step["action"].startswith("send_")]
        assert payload_steps
        for step in payload_steps:
            payload = step.get("payload")
            assert payload
            assert payload["payload"] == TRANSFER_PAYLOAD
            if step["command"] is not None:
                assert step["command"] == TRANSFER_PAYLOAD

        for step in case["steps"]:
            expected = step.get("expected")
            if isinstance(expected, dict) and "value" in expected:
                assert expected["value"] == TRANSFER_PAYLOAD


def test_phase5_fixed_and_broadcast_payloads_are_structured() -> None:
    cases = {case["id"]: case for case in load_formal_case_directory(FORMAL_CASE_DIR)}

    for case_id in ("MAIN-003", "MAIN-004"):
        payload_steps = [step for step in cases[case_id]["steps"] if step["action"] == "send_fixed_payload"]
        assert len(payload_steps) == 2
        for step in payload_steps:
            assert step["payload"] == {
                "target_mac": "00,02",
                "channel": "01",
                "payload": TRANSFER_PAYLOAD,
                "encoding": "fixed_hex_frame",
            }

    for case_id in ("MAIN-005", "MAIN-006"):
        payload_steps = [step for step in cases[case_id]["steps"] if step["action"] == "send_broadcast_payload"]
        assert len(payload_steps) == 2
        for step in payload_steps:
            assert step["payload"] == {
                "channel": "01",
                "payload": TRANSFER_PAYLOAD,
                "encoding": "broadcast_hex_frame",
            }
        receiver_asserts = [
            step for step in cases[case_id]["steps"] if step["action"] == "multi_receiver_assert"
        ]
        assert len(receiver_asserts) == 2
        assert all(step["expected"]["receivers"] == ["B", "C"] for step in receiver_asserts)


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
        expected_error = "ERROR=101" if index <= 13 else "ERROR=101"
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

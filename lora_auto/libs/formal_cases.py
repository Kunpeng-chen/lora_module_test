"""Loader and validation helpers for formal LoRa test case YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class FormalCaseError(ValueError):
    """Raised when a formal case file or case entry is invalid."""


REQUIRED_CASE_FIELDS = frozenset(
    {
        "id",
        "suite",
        "feature",
        "scenario",
        "priority",
        "automation_level",
        "devices",
        "preconditions",
        "steps",
        "expected",
        "result_policy",
        "evidence",
        "metadata",
    }
)

VALID_PRIORITIES = frozenset({"P0", "P1", "P2"})
VALID_AUTOMATION_LEVELS = frozenset({"auto", "semi_auto", "manual"})
VALID_RUN_POLICIES = frozenset({"auto", "manual_confirm", "skip_by_default"})
FORMAL_CASE_FILENAMES = (
    "main_cases.yaml",
    "at_cases.yaml",
    "error_at_cases.yaml",
    "ship_cases.yaml",
    "iter_cases.yaml",
)


def load_formal_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load and validate formal cases from one YAML file."""

    file_path = Path(path)
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except OSError as exc:
        raise FormalCaseError(f"failed to read formal case file {file_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise FormalCaseError(f"formal case file {file_path} must contain a mapping")

    cases = extract_formal_cases(data, source=str(file_path))
    if not isinstance(cases, list) or not cases:
        raise FormalCaseError(
            f"formal case file {file_path} must contain a non-empty 'cases' list or 'error_at_cases' list"
        )

    validate_formal_cases(cases, source=str(file_path))
    return cases


def extract_formal_cases(data: dict[str, Any], source: str = "formal cases") -> list[dict[str, Any]]:
    """Extract regular cases or expand a compact formal error-AT matrix."""

    error_at_cases = data.get("error_at_cases")
    if error_at_cases is not None:
        if data.get("cases") not in (None, []):
            raise FormalCaseError(f"{source} must not mix 'cases' and 'error_at_cases'")
        return expand_error_at_cases(error_at_cases, source=source)

    return data.get("cases")


def expand_error_at_cases(items: Any, source: str = "formal error AT cases") -> list[dict[str, Any]]:
    """Expand compact ERRAT matrix rows into full formal case mappings."""

    if not isinstance(items, list) or not items:
        raise FormalCaseError(f"{source} error_at_cases must be a non-empty list")

    cases: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise FormalCaseError(f"error_at_cases row #{index + 1} in {source} must be a mapping")

        case_id = _required_matrix_string(item, "id", index, source)
        feature = _required_matrix_string(item, "feature", index, source)
        command = _required_matrix_string(item, "command", index, source)
        expected_error = _required_matrix_string(item, "expected_error", index, source)
        scenario = _required_matrix_string(item, "scenario", index, source)

        if expected_error not in {"ERROR=101"}:
            raise FormalCaseError(
                f"error_at_cases row {case_id!r} in {source} has unsupported expected_error {expected_error!r}"
            )

        cases.append(
            {
                "id": case_id,
                "suite": "error_at",
                "feature": feature,
                "scenario": f"{scenario} returns {expected_error}",
                "priority": "P1",
                "automation_level": "auto",
                "devices": ["A"],
                "preconditions": [
                    "Device A is connected; runner will ensure AT mode before execution."
                ],
                "steps": [
                    {
                        "action": "send_at",
                        "device": "A",
                        "command": command,
                        "expected": {"mode": "contains", "value": expected_error},
                    },
                    {
                        "action": "post_check",
                        "device": "A",
                        "command": "AT",
                        "expected": {"mode": "contains", "value": "OK"},
                    },
                ],
                "expected": [
                    f"Invalid command returns {expected_error} and the module remains responsive."
                ],
                "result_policy": {
                    "pass_when": [
                        f"The invalid command returns {expected_error}.",
                        "The post-check AT command returns OK.",
                    ],
                    "fail_when": [
                        f"The invalid command does not return {expected_error}.",
                        "The post-check AT command does not return OK.",
                    ],
                },
                "evidence": {
                    "serial_log": None,
                    "logic_analyzer": None,
                    "power_record": None,
                    "rf_record": None,
                    "manual_note": None,
                },
                "metadata": {
                    "source": "formal-test-case-design-plan Phase 4",
                    "manual_ref": "docs/manual/dx-lr31-900t22s-uart-application-guide.md#error-code-policy",
                    "destructive": False,
                    "state_changing": False,
                    "run_policy": "auto",
                },
            }
        )

    return cases


def load_formal_case_directory(path: str | Path) -> list[dict[str, Any]]:
    """Load all standard formal case YAML files from a directory."""

    directory = Path(path)
    cases: list[dict[str, Any]] = []
    for filename in FORMAL_CASE_FILENAMES:
        file_path = directory / filename
        if not file_path.exists():
            raise FormalCaseError(f"formal case file {file_path} does not exist")
        cases.extend(load_formal_cases(file_path))

    validate_unique_case_ids(cases)
    return cases


def validate_formal_cases(cases: list[dict[str, Any]], source: str = "formal cases") -> None:
    """Validate required fields, field enums, metadata, and duplicate IDs."""

    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise FormalCaseError(f"case #{index + 1} in {source} must be a mapping")
        validate_formal_case(case, source=source)
    validate_unique_case_ids(cases)


def validate_formal_case(case: dict[str, Any], source: str = "formal cases") -> None:
    """Validate one formal case mapping."""

    case_id = case.get("id", "<missing id>")
    missing = sorted(REQUIRED_CASE_FIELDS.difference(case))
    if missing:
        raise FormalCaseError(f"case {case_id!r} in {source} is missing required fields: {', '.join(missing)}")

    if case["priority"] not in VALID_PRIORITIES:
        raise FormalCaseError(f"case {case_id!r} has invalid priority {case['priority']!r}")

    if case["automation_level"] not in VALID_AUTOMATION_LEVELS:
        raise FormalCaseError(
            f"case {case_id!r} has invalid automation_level {case['automation_level']!r}"
        )

    _validate_string(case, "id", source)
    _validate_string(case, "suite", source)
    _validate_string(case, "feature", source)
    _validate_string(case, "scenario", source)
    _validate_list(case, "devices", source, allow_empty=False)
    _validate_list(case, "preconditions", source, allow_empty=True)
    _validate_list(case, "steps", source, allow_empty=False)
    _validate_list(case, "expected", source, allow_empty=False)

    result_policy = _validate_mapping(case, "result_policy", source)
    for policy_field in ("pass_when", "fail_when"):
        if policy_field not in result_policy or not isinstance(result_policy[policy_field], list):
            raise FormalCaseError(f"case {case_id!r} result_policy.{policy_field} must be a list")

    _validate_mapping(case, "evidence", source)
    metadata = _validate_mapping(case, "metadata", source)
    _validate_metadata(case_id, metadata)

    for step_index, step in enumerate(case["steps"]):
        if not isinstance(step, dict):
            raise FormalCaseError(f"case {case_id!r} step #{step_index + 1} must be a mapping")
        if "action" not in step or not isinstance(step["action"], str) or not step["action"]:
            raise FormalCaseError(f"case {case_id!r} step #{step_index + 1} must include non-empty action")


def validate_unique_case_ids(cases: list[dict[str, Any]]) -> None:
    """Ensure formal case IDs are unique within a file or loaded collection."""

    seen: set[str] = set()
    for case in cases:
        case_id = str(case.get("id", ""))
        if case_id in seen:
            raise FormalCaseError(f"duplicate formal case id: {case_id}")
        seen.add(case_id)


def _required_matrix_string(item: dict[str, Any], field: str, index: int, source: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value:
        raise FormalCaseError(
            f"error_at_cases row #{index + 1} in {source} field {field!r} must be a non-empty string"
        )
    return value


def _validate_metadata(case_id: str, metadata: dict[str, Any]) -> None:
    required_metadata = {"source", "manual_ref", "destructive", "state_changing", "run_policy"}
    missing = sorted(required_metadata.difference(metadata))
    if missing:
        raise FormalCaseError(
            f"case {case_id!r} metadata is missing required fields: {', '.join(missing)}"
        )

    if not isinstance(metadata["destructive"], bool):
        raise FormalCaseError(f"case {case_id!r} metadata.destructive must be a bool")
    if not isinstance(metadata["state_changing"], bool):
        raise FormalCaseError(f"case {case_id!r} metadata.state_changing must be a bool")
    if metadata["run_policy"] not in VALID_RUN_POLICIES:
        raise FormalCaseError(f"case {case_id!r} has invalid run_policy {metadata['run_policy']!r}")
    if metadata["destructive"] and metadata["run_policy"] == "auto":
        raise FormalCaseError(f"case {case_id!r} is destructive and must not use run_policy 'auto'")


def _validate_string(case: dict[str, Any], field: str, source: str) -> None:
    if not isinstance(case[field], str) or not case[field]:
        raise FormalCaseError(f"case {case.get('id', '<missing id>')!r} in {source} field {field!r} must be a non-empty string")


def _validate_list(case: dict[str, Any], field: str, source: str, allow_empty: bool) -> None:
    value = case[field]
    if not isinstance(value, list) or (not allow_empty and not value):
        raise FormalCaseError(f"case {case.get('id', '<missing id>')!r} in {source} field {field!r} must be a list")


def _validate_mapping(case: dict[str, Any], field: str, source: str) -> dict[str, Any]:
    value = case[field]
    if not isinstance(value, dict):
        raise FormalCaseError(f"case {case.get('id', '<missing id>')!r} in {source} field {field!r} must be a mapping")
    return value

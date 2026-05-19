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

    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FormalCaseError(f"formal case file {file_path} must contain a non-empty 'cases' list")

    validate_formal_cases(cases, source=str(file_path))
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

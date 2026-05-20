from pathlib import Path

from lora_auto.libs.formal_cases import load_formal_case_directory

FORMAL_CASE_DIR = Path(__file__).resolve().parents[1] / "lora_auto" / "config" / "formal"


def test_error_at_case_count():
    cases = [case for case in load_formal_case_directory(FORMAL_CASE_DIR) if case["suite"] == "error_at"]
    assert len(cases) == 57

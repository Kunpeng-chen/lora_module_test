from __future__ import annotations

import json
from pathlib import Path

from lora_auto.libs.report import (
    ReportCase,
    ReportStep,
    build_summary,
    write_device_log,
    write_json_report,
    write_markdown_report,
    write_reports,
)


def make_cases() -> list[ReportCase]:
    return [
        ReportCase(
            case_id="MVP-001",
            case_name="AT 基础指令测试",
            status="PASS",
            start_time="2026-05-18T00:00:00Z",
            end_time="2026-05-18T00:00:01Z",
            duration=1.0,
            steps=[ReportStep(name="AT", status="PASS", detail="OK")],
            log_file="reports/logs/MVP-001_runner.log",
        ),
        ReportCase(
            case_id="MVP-003",
            case_name="透明传输收发一致性测试",
            status="FAIL",
            start_time="2026-05-18T00:00:02Z",
            end_time="2026-05-18T00:00:03Z",
            duration=1.0,
            failure_reason="receiver did not receive expected payload",
            log_file="reports/logs/MVP-003_runner.log",
        ),
    ]


def test_build_summary_counts_case_statuses() -> None:
    summary = build_summary(make_cases())

    assert summary == {"total": 2, "passed": 1, "failed": 1, "blocked": 0}


def test_write_device_log_creates_log_file(tmp_path: Path) -> None:
    log_path = write_device_log(tmp_path, "MVP-001", "A", ["TX: AT", "RX: OK"])

    path = Path(log_path)
    assert path.exists()
    assert path.name == "MVP-001_A.log"
    assert "TX: AT" in path.read_text(encoding="utf-8")


def test_write_json_report_creates_structured_result(tmp_path: Path) -> None:
    report_path = write_json_report(tmp_path, make_cases())

    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["failed"] == 1
    assert payload["cases"][0]["case_id"] == "MVP-001"
    assert payload["cases"][1]["failure_reason"] == "receiver did not receive expected payload"


def test_write_markdown_report_creates_result_table(tmp_path: Path) -> None:
    report_path = write_markdown_report(tmp_path, make_cases())

    content = Path(report_path).read_text(encoding="utf-8")
    assert "# LoRa 自动化测试报告" in content
    assert "| MVP-001 | AT 基础指令测试 | PASS" in content
    assert "| MVP-003 | 透明传输收发一致性测试 | FAIL" in content


def test_write_reports_returns_json_and_markdown_paths(tmp_path: Path) -> None:
    json_path, markdown_path = write_reports(tmp_path, make_cases())

    assert Path(json_path).name == "result.json"
    assert Path(markdown_path).name == "result.md"
    assert Path(json_path).exists()
    assert Path(markdown_path).exists()

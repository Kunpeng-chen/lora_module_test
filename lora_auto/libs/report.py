"""Report generation helpers for LoRa automation MVP runs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ReportStep:
    """One step item in a test case report."""

    name: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class ReportCase:
    """Serializable test case report entry."""

    case_id: str
    case_name: str
    status: str
    start_time: str
    end_time: str
    duration: float
    steps: list[ReportStep] = field(default_factory=list)
    failure_reason: str | None = None
    log_file: str | None = None


def utc_now_iso() -> str:
    """Return an ISO timestamp without requiring external dependencies."""

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_report_dirs(report_dir: str | Path) -> Path:
    """Create report root and logs subdirectory."""

    root = Path(report_dir)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    return root


def write_device_log(report_dir: str | Path, case_id: str, device_name: str, lines: Iterable[str]) -> str:
    """Write a simple per-case device log and return its path as a string."""

    root = ensure_report_dirs(report_dir)
    log_path = root / "logs" / f"{case_id}_{device_name}.log"
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(log_path)


def write_json_report(report_dir: str | Path, cases: list[ReportCase]) -> str:
    """Write reports/result.json."""

    root = ensure_report_dirs(report_dir)
    path = root / "result.json"
    payload = {
        "summary": build_summary(cases),
        "cases": [asdict(case) for case in cases],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def write_markdown_report(report_dir: str | Path, cases: list[ReportCase]) -> str:
    """Write reports/result.md."""

    root = ensure_report_dirs(report_dir)
    path = root / "result.md"
    summary = build_summary(cases)
    lines = [
        "# LoRa 自动化测试报告",
        "",
        "## 测试概览",
        "",
        "| 总数 | 通过 | 失败 | 阻塞 |",
        "|---:|---:|---:|---:|",
        f"| {summary['total']} | {summary['passed']} | {summary['failed']} | {summary['blocked']} |",
        "",
        "## 用例结果",
        "",
        "| 用例ID | 用例名称 | 结果 | 耗时 | 失败原因 | 日志 |",
        "|---|---|---|---:|---|---|",
    ]
    for case in cases:
        failure = case.failure_reason or "-"
        log_file = case.log_file or "-"
        lines.append(
            f"| {case.case_id} | {case.case_name} | {case.status} | {case.duration:.3f}s | {failure} | {log_file} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def write_reports(report_dir: str | Path, cases: list[ReportCase]) -> tuple[str, str]:
    """Write JSON and Markdown reports."""

    json_path = write_json_report(report_dir, cases)
    markdown_path = write_markdown_report(report_dir, cases)
    return json_path, markdown_path


def build_summary(cases: list[ReportCase]) -> dict[str, int]:
    """Build pass/fail summary counts."""

    passed = sum(1 for case in cases if case.status == "PASS")
    failed = sum(1 for case in cases if case.status == "FAIL")
    blocked = sum(1 for case in cases if case.status == "BLOCKED")
    return {
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
    }

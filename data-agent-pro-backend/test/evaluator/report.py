import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from test.evaluator.schemas import EvalCaseResult, EvalSummary


def create_run_report_dir(report_root_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = report_root_dir / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def write_json_report(report_dir: Path, summary: EvalSummary, results: list[EvalCaseResult]) -> Path:
    report_path = report_dir / "eval_report.json"
    payload = {
        "summary": asdict(summary),
        "results": [asdict(result) for result in results],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report_path


def write_markdown_report(report_dir: Path, summary: EvalSummary, results: list[EvalCaseResult]) -> Path:
    report_path = report_dir / "eval_report.md"

    lines = [
        "# NL2SQL 评测报告",
        "",
        "## 召回层",
        "",
        *format_metric_lines(summary.retrieval_layer),
        "",
        "## 筛选层",
        "",
        *format_metric_lines(summary.filtering_layer),
        "",
        "## SQL 层",
        "",
        *format_metric_lines(summary.sql_layer),
        "",
        "## 结果层",
        "",
        *format_metric_lines(summary.result_layer),
        "",
        "## 性能与成本层",
        "",
        *format_metric_lines(summary.performance_layer),
        "",
        "## 明细",
        "",
        "| ID | 问题 | 召回表 | 召回字段 | 筛选表 | 筛选字段 | 语法 | 执行 | 语义结果 | 严格结果 | F1 | 耗时(ms) | 错误归因 | 错误 | Trace |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]

    for result in results:
        error = (result.error or "").replace("|", "\\|").replace("\n", " ")[:200]
        lines.append(
            f"| {result.id} | {result.question} | {icon(result.table_recall)} | "
            f"{icon(result.column_recall)} | {icon(result.filtered_table_accuracy)} | "
            f"{icon(result.filtered_column_accuracy)} | {icon(result.syntax_valid)} | "
            f"{icon(result.execution_success)} | {icon(result.execution_accuracy)} | "
            f"{icon(result.strict_execution_accuracy)} | {result.result_set_f1:.2f} | "
            f"{result.latency_ms:.2f} | {result.error_type or ''} | {error} | {result.trace_file or ''} |"
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def icon(value: bool) -> str:
    return "✅" if value else "❌"


def format_metric_lines(metrics: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in metrics.items():
        if isinstance(value, dict):
            lines.append(f"### {format_section_title(key)}")
            lines.append("")
            lines.extend(format_metric_lines(value))
            lines.append("")
        elif key.endswith("_ms") or key.endswith("_ms_avg"):
            lines.append(f"- `{key}`：{value} ms")
        elif "rate" in key or "accuracy" in key or "recall" in key or "precision" in key or key.endswith("_f1_avg") or key.startswith(("column@", "metric@", "value@", "table@")) or key in {"column", "metric", "value"}:
            lines.append(f"- `{key}`：{value:.2%}")
        else:
            lines.append(f"- `{key}`：{value}")
    return lines


def format_section_title(key: str) -> str:
    return {
        "recall": "召回率 Recall",
        "precision": "精确率 Precision",
        "mrr": "排序质量 MRR",
    }.get(key, key)
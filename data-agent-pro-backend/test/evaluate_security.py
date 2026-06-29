"""
AST 安全校验独立评测模块。

用法:
    python -m test.evaluate_security
    python -m test.evaluate_security --cases test/security_eval_cases.json
"""

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.sql_security import validate_select_sql_security
from app.config.meta_config import meta_config


@dataclass
class SecurityEvalCase:
    id: str
    description: str
    sql: str
    expected_valid: bool
    expected_rule: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SecurityEvalCase":
        return cls(
            id=data["id"],
            description=data["description"],
            sql=data["sql"],
            expected_valid=data["expected_valid"],
            expected_rule=data.get("expected_rule"),
        )


@dataclass
class SecurityEvalResult:
    id: str
    description: str
    sql: str
    expected_valid: bool
    actual_valid: bool
    expected_rule: str | None
    actual_rule: str | None
    passed: bool
    error_message: str | None = None


def load_cases(path: Path) -> list[SecurityEvalCase]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [SecurityEvalCase.from_dict(item) for item in raw]


def build_table_infos() -> list[dict]:
    """从 meta_config 构建安全校验所需的 table_infos。"""
    table_infos: list[dict] = []
    for table in meta_config.tables or []:
        table_infos.append(
            {
                "name": table.name,
                "columns": [{"name": col.name} for col in table.columns],
            }
        )
    return table_infos


def classify_rule(error: str | None) -> str | None:
    """从安全校验错误信息中提取规则编码。"""
    if not error:
        return None
    rules = [
        ("SQL 解析失败", "sql_parse_error"),
        ("禁止多语句执行", "multi_statement"),
        ("只允许单条 SELECT", "non_select_statement"),
        ("禁止执行", "prohibited_statement"),
        ("禁止 SELECT *", "select_star"),
        ("疑似恶意 SQL", "malicious_sql"),
        ("禁止访问指定库名", "unauthorized_catalog"),
        ("禁止访问未授权表", "unauthorized_table"),
        ("禁止访问未授权字段", "unauthorized_column"),
        ("SELECT 必须显式指定 FROM", "missing_from"),
        ("未找到可授权访问的表", "no_authorized_tables"),
    ]
    for keyword, code in rules:
        if keyword in error:
            return code
    return "unknown"


def run_security_eval(cases: list[SecurityEvalCase]) -> list[SecurityEvalResult]:
    table_infos = build_table_infos()
    results: list[SecurityEvalResult] = []
    for case in cases:
        result = validate_select_sql_security(case.sql, table_infos)
        actual_rule = None if result.valid else classify_rule(result.error)
        passed = (result.valid == case.expected_valid) and (
            case.expected_rule is None or actual_rule == case.expected_rule
        )
        results.append(
            SecurityEvalResult(
                id=case.id,
                description=case.description,
                sql=case.sql,
                expected_valid=case.expected_valid,
                actual_valid=result.valid,
                expected_rule=case.expected_rule,
                actual_rule=actual_rule,
                passed=passed,
                error_message=result.error if not result.valid else None,
            )
        )
    return results


def write_report(
    results: list[SecurityEvalResult],
    report_dir: Path,
) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "security_eval_report.json"
    md_path = report_dir / "security_eval_report.md"

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": f"{passed / total:.2%}" if total > 0 else "0%",
    }

    json_path.write_text(
        json.dumps(
            {"summary": summary, "results": [asdict(r) for r in results]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    md_lines = [
        "# AST 安全校验评测报告",
        "",
        f"- 总用例数：{total}",
        f"- 通过：{passed}",
        f"- 失败：{total - passed}",
        f"- 通过率：{summary['pass_rate']}",
        "",
        "## 明细",
        "",
        "| ID | 描述 | 期望通过 | 实际通过 | 期望规则 | 实际规则 | 结果 | 错误信息 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        err = (r.error_message or "").replace("|", "\\|").replace("\n", " ")[:120]
        md_lines.append(
            f"| {r.id} | {r.description} | {'✅' if r.expected_valid else '❌'} | "
            f"{'✅' if r.actual_valid else '❌'} | {r.expected_rule or ''} | "
            f"{r.actual_rule or ''} | {'✅' if r.passed else '❌'} | {err} |"
        )
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AST security validation evaluation.")
    parser.add_argument("--cases", type=Path, default=Path("test/security_eval_cases.json"))
    parser.add_argument("--report-dir", type=Path, default=Path("test/reports"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases)
    results = run_security_eval(cases)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = args.report_dir / f"security_{timestamp}"
    json_path, md_path = write_report(results, report_dir)
    passed = sum(1 for r in results if r.passed)
    print(f"AST 安全校验评测完成：{len(results)} 条用例，通过 {passed} 条")
    print(f"报告目录：{report_dir}")


if __name__ == "__main__":
    main()

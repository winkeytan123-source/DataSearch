import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.core.failure_case import classify_sql_error
from app.core.trace_collector import safe_filename
from test.evaluator.schemas import EvalCase, EvalCaseResult


def infer_error_type(result: EvalCaseResult) -> str | None:
    if result.syntax_valid and result.execution_success and result.execution_accuracy:
        return None
    if result.error and "[EXCEED_STEP_LIMIT]" in result.error:
        return "exceed_step_limit"
    if not result.column_recall:
        return "column_recall_miss"
    if not result.value_recall:
        return "value_recall_miss"
    if not result.metric_recall:
        return "metric_recall_miss"
    if not result.filtered_column_accuracy or not result.filtered_table_accuracy:
        return "filter_loss"
    if not result.syntax_valid:
        return classify_sql_error(result.error)
    if not result.execution_success:
        return "execution_error"
    if not result.execution_accuracy:
        return "result_mismatch"
    return None


def write_failure_case(
    case: EvalCase,
    result: EvalCaseResult,
    failure_root_dir: Path | None = None,
) -> Path | None:
    error_type = result.error_type or infer_error_type(result)
    if not error_type:
        return None

    root_dir = failure_root_dir or Path("test/failure_cases/pending")
    root_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    failure_path = root_dir / f"{timestamp}_{safe_filename(case.id)}.json"
    payload = {
        "id": f"auto_{timestamp}_{case.id}",
        "source": "evaluation",
        "request_id": result.request_id or extract_request_id_from_trace_file(result.trace_file),
        "question": case.question,
        "generated_sql": result.generated_sql,
        "error_type": error_type,
        "error_message": result.error,
        "gold_sql": case.gold_sql,
        "expected_tables": case.expected_tables,
        "expected_columns": case.expected_columns,
        "expected_metrics": case.expected_metrics,
        "expected_values": case.expected_values,
        "expected_conditions": case.expected_conditions,
        "numeric_tolerance": case.numeric_tolerance,
        "trace_file": result.trace_file,
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "eval_result": asdict(result),
    }
    failure_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return failure_path


def extract_request_id_from_trace_file(trace_file: str | None) -> str | None:
    if not trace_file:
        return None
    return Path(trace_file).stem
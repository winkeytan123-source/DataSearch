"""在线数据飞轮：失败样例沉淀模块。

当在线查询出现错误或未返回结果时，自动将失败样例写入
test/failure_cases/pending/ 目录，供后续人工审核与回灌评测集。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.trace_collector import TraceCollector, backend_root, safe_filename


# ── 错误分类 ────────────────────────────────────────────────


def classify_sql_error(error: str | None) -> str:
    """将 SQL 校验失败进一步归类为 AST 安全校验子类或通用校验错误。"""
    if not error:
        return "sql_validation_error"
    if "[EXCEED_STEP_LIMIT]" in error:
        return "exceed_step_limit"
    if "[AST_SECURITY]" not in error:
        return "sql_validation_error"
    message = error.replace("[AST_SECURITY]", "").strip()
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
    for keyword, error_code in rules:
        if keyword in message:
            return f"ast_security:{error_code}"
    return "ast_security:unknown"


def infer_online_error_type(
    error: str | None,
    sql_valid: bool | None,
    has_result: bool,
) -> str | None:
    """从在线查询的 trace 信息推断错误类型。

    返回 None 表示查询成功，不需要沉淀失败样例。
    """
    # 查询成功
    if error is None and has_result:
        return None

    # SQL 自动更正超过上限
    if error and "[EXCEED_STEP_LIMIT]" in error:
        return "exceed_step_limit"

    # AST 安全校验拦截
    if error and "[AST_SECURITY]" in error:
        return classify_sql_error(error)

    # SQL 执行报错（MySQL OperationalError 等）
    if error and ("OperationalError" in error or "ProgrammingError" in error):
        return "execution_error"

    # 其他系统异常
    if error:
        return "system_error"

    # 没有异常但也没有结果（极端边界）
    if not has_result:
        return "no_result"

    return None


# ── 在线失败样例写入 ──────────────────────────────────────────


def write_online_failure_case(
    trace_collector: TraceCollector,
    error: str | None,
    failure_root_dir: Path | None = None,
) -> Path | None:
    """在线查询失败时，将失败样例写入 pending 目录。

    Args:
        trace_collector: 本次查询的 TraceCollector 实例（已完成 finish_query）。
        error: 最终错误信息（None 表示无异常抛出）。
        failure_root_dir: 失败样例根目录，默认为 test/failure_cases/pending。

    Returns:
        写入的文件路径；如果查询成功则返回 None。
    """
    has_result = trace_collector.execution_result_digest is not None
    error_type = infer_online_error_type(error, trace_collector.sql_valid, has_result)
    if not error_type:
        return None

    root_dir = failure_root_dir or backend_root() / "test" / "failure_cases" / "pending"
    root_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    request_id = safe_filename(trace_collector.request_id or "unknown")
    failure_path = root_dir / f"{timestamp}_online_{request_id}.json"

    payload: dict[str, Any] = {
        "id": f"auto_{timestamp}_online_{request_id}",
        "source": "online",
        "request_id": trace_collector.request_id,
        "question": trace_collector.query,
        "generated_sql": trace_collector.final_sql,
        "error_type": error_type,
        "error_message": error,
        "trace_file": trace_collector.trace_file,
        "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "trace_summary": {
            "sql_valid": trace_collector.sql_valid,
            "has_result": has_result,
            "total_latency_ms": trace_collector.total_latency_ms,
            "retrieval_traces_count": len(trace_collector.retrieval_traces),
            "source": trace_collector.source,
        },
    }
    failure_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return failure_path

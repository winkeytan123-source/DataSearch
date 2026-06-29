import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class TraceCollector:
    request_id: str | None = None
    query: str | None = None
    user_scope: dict[str, Any] = field(default_factory=dict)
    source: str | None = None
    retrieval_traces: list[dict[str, Any]] = field(default_factory=list)
    final_sql: str | None = None
    sql_valid: bool | None = None
    execution_result_digest: dict[str, Any] | None = None
    total_latency_ms: float | None = None
    error: str | None = None
    created_at: str | None = None
    finished_at: str | None = None
    trace_file: str | None = None
    _start_time: float | None = None

    def start_query(
        self,
        request_id: str,
        query: str,
        user_scope: dict[str, Any] | None = None,
        source: str | None = None,
    ) -> None:
        self.request_id = request_id
        self.query = query
        self.user_scope = user_scope or {}
        self.source = source
        self.created_at = datetime.now().isoformat(timespec="seconds")
        self._start_time = time.perf_counter()

    def add_retrieval_trace(
        self,
        node: str,
        keyword: str,
        channel: str,
        limit: int,
        results: list[dict[str, Any]],
    ) -> None:
        self.retrieval_traces.append(
            {
                "node": node,
                "keyword": keyword,
                "channel": channel,
                "limit": limit,
                "results": results,
            }
        )

    def set_sql_validation(self, sql: str | None, valid: bool, error: str | None = None) -> None:
        self.final_sql = sql
        self.sql_valid = valid
        if error:
            self.error = error

    def set_execution_result(self, result: list[dict[str, Any]] | None) -> None:
        self.execution_result_digest = build_result_digest(result)

    def finish_query(
        self,
        final_sql: str | None = None,
        sql_valid: bool | None = None,
        error: str | None = None,
        total_latency_ms: float | None = None,
    ) -> None:
        if final_sql is not None:
            self.final_sql = final_sql
        if sql_valid is not None:
            self.sql_valid = sql_valid
        if error is not None:
            self.error = error
        if total_latency_ms is not None:
            self.total_latency_ms = round(total_latency_ms, 2)
        elif self._start_time is not None:
            self.total_latency_ms = round((time.perf_counter() - self._start_time) * 1000, 2)
        self.finished_at = datetime.now().isoformat(timespec="seconds")

    def save_to_file(self, trace_root_dir: Path | str | None = None) -> Path:
        if self.finished_at is None:
            self.finish_query()

        root_dir = Path(trace_root_dir) if trace_root_dir else backend_root() / "logs" / "traces"
        date_part = datetime.fromisoformat(self.created_at).strftime("%Y%m%d") if self.created_at else datetime.now().strftime("%Y%m%d")
        request_id = safe_filename(self.request_id or "unknown_request")
        trace_dir = root_dir / date_part
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"{request_id}.json"
        self.trace_file = str(trace_path)
        trace_path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return trace_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "user_scope": self.user_scope,
            "source": self.source,
            "retrieval_traces": self.retrieval_traces,
            "final_sql": self.final_sql,
            "sql_valid": self.sql_valid,
            "execution_result_digest": self.execution_result_digest,
            "total_latency_ms": self.total_latency_ms,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "trace_file": self.trace_file,
        }


def build_ranked_results(payloads: list[dict[str, Any]], score_getter=None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        result = {"rank": index, "payload": payload}
        if score_getter is not None:
            result["score"] = score_getter(payload)
        results.append(result)
    return results


def build_result_digest(result: list[dict[str, Any]] | None) -> dict[str, Any]:
    if result is None:
        return {"row_count": 0, "columns": [], "preview": []}
    columns: list[str] = []
    if result:
        columns = list(result[0].keys())
    return {
        "row_count": len(result),
        "columns": columns,
        "preview": result[:5],
    }


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
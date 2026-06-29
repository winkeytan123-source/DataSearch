from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalCase:
    id: str
    question: str
    gold_sql: str
    expected_tables: list[str] = field(default_factory=list)
    expected_columns: list[str] = field(default_factory=list)
    expected_metrics: list[str] = field(default_factory=list)
    expected_values: list[str] = field(default_factory=list)
    expected_conditions: list[str] = field(default_factory=list)
    numeric_tolerance: float = 0.01
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        return cls(
            id=data["id"],
            question=data["question"],
            gold_sql=data["gold_sql"],
            expected_tables=data.get("expected_tables", []),
            expected_columns=data.get("expected_columns", []),
            expected_metrics=data.get("expected_metrics", []),
            expected_values=data.get("expected_values", []),
            expected_conditions=data.get("expected_conditions", []),
            numeric_tolerance=data.get("numeric_tolerance", 0.01),
            tags=data.get("tags", []),
        )


@dataclass
class EvalCaseResult:
    id: str
    question: str
    gold_sql: str
    generated_sql: str | None
    gold_result: list[dict[str, Any]] | None
    generated_result: list[dict[str, Any]] | None
    syntax_valid: bool
    execution_success: bool
    strict_execution_accuracy: bool
    execution_accuracy: bool
    numeric_tolerance_accuracy: bool
    result_set_f1: float
    column_recall: bool
    column_precision: float
    metric_recall: bool
    value_recall: bool
    value_precision: float
    table_recall: bool
    retrieval_metrics: dict[str, float]
    retrieval_traces: list[dict[str, Any]]
    filtered_table_accuracy: bool
    filtered_column_accuracy: bool
    context_compression_ratio: float | None
    context_loss_rate: float
    sql_exact_match: bool
    table_match: bool
    column_match: bool
    condition_match: bool
    aggregation_match: bool
    retrieval_latency_ms: float | None
    sql_generation_latency_ms: float | None
    sql_execution_latency_ms: float | None
    latency_ms: float
    request_id: str | None = None
    trace_file: str | None = None
    error_type: str | None = None
    error: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalSummary:
    total: int
    retrieval_layer: dict[str, Any]
    filtering_layer: dict[str, float]
    sql_layer: dict[str, float]
    result_layer: dict[str, float]
    performance_layer: dict[str, float]
from statistics import mean
from typing import Any

from test.evaluator.schemas import EvalCaseResult, EvalSummary


def rate(results: list[EvalCaseResult], attr: str) -> float:
    if not results:
        return 0.0
    return round(sum(1 for result in results if getattr(result, attr)) / len(results), 4)


def avg(results: list[EvalCaseResult], attr: str) -> float:
    values = [getattr(result, attr) for result in results if getattr(result, attr) is not None]
    if not values:
        return 0.0
    return round(mean(values), 4)


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int(round((len(sorted_values) - 1) * percent))
    return round(sorted_values[index], 2)


def summarize(results: list[EvalCaseResult]) -> EvalSummary:
    latencies = [result.latency_ms for result in results]
    retrieval_latencies = [result.retrieval_latency_ms for result in results if result.retrieval_latency_ms is not None]
    sql_generation_latencies = [result.sql_generation_latency_ms for result in results if result.sql_generation_latency_ms is not None]
    sql_execution_latencies = [result.sql_execution_latency_ms for result in results if result.sql_execution_latency_ms is not None]
    retrieval_layer = aggregate_retrieval_metrics(results)

    return EvalSummary(
        total=len(results),
        retrieval_layer=retrieval_layer,
        filtering_layer={
            "filtered_table_accuracy": rate(results, "filtered_table_accuracy"),
            "filtered_column_accuracy": rate(results, "filtered_column_accuracy"),
            "context_compression_ratio_avg": avg(results, "context_compression_ratio"),
            "context_loss_rate_avg": avg(results, "context_loss_rate"),
        },
        sql_layer={
            "syntax_valid_rate": rate(results, "syntax_valid"),
            "executable_rate": rate(results, "execution_success"),
            "sql_exact_match_rate": rate(results, "sql_exact_match"),
            "table_match_rate": rate(results, "table_match"),
            "column_match_rate": rate(results, "column_match"),
            "where_condition_match_rate": rate(results, "condition_match"),
            "aggregation_match_rate": rate(results, "aggregation_match"),
        },
        result_layer={
            "strict_execution_accuracy": rate(results, "strict_execution_accuracy"),
            "execution_accuracy": rate(results, "execution_accuracy"),
            "numeric_tolerance_accuracy": rate(results, "numeric_tolerance_accuracy"),
            "result_set_f1_avg": avg(results, "result_set_f1"),
        },
        performance_layer={
            "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
            "p95_latency_ms": percentile(latencies, 0.95),
            "retrieval_latency_ms_avg": round(mean(retrieval_latencies), 2) if retrieval_latencies else 0.0,
            "sql_generation_latency_ms_avg": round(mean(sql_generation_latencies), 2) if sql_generation_latencies else 0.0,
            "sql_execution_latency_ms_avg": round(mean(sql_execution_latencies), 2) if sql_execution_latencies else 0.0,
            "llm_call_count": 0.0,
            "prompt_tokens": 0.0,
            "completion_tokens": 0.0,
            "cost_per_query": 0.0,
        },
    )


def aggregate_retrieval_metrics(results: list[EvalCaseResult]) -> dict[str, Any]:
    retrieval_layer: dict[str, Any] = {
        "recall": {},
        "precision": {},
        "mrr": {},
    }
    for section in retrieval_layer:
        metric_names = sorted(
            {
                name
                for result in results
                for name in result.retrieval_metrics.get(section, {})
            }
        )
        for name in metric_names:
            values = [
                result.retrieval_metrics[section][name]
                for result in results
                if name in result.retrieval_metrics.get(section, {})
            ]
            retrieval_layer[section][name] = round(mean(values), 4) if values else 0.0
    return retrieval_layer
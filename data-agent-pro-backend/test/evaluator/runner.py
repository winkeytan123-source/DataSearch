import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import dw_mysql_client_manager, meta_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.core.context import request_id_context_var
from app.core.trace_collector import TraceCollector
from app.repository.es.value_es_repository import ValueESRepository
from app.repository.mysql.dw_mysql_repository import DWMySQLRepository
from app.repository.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repository.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repository.qdrant.metric_qdrant_repository import MetricQdrantRepository
from test.evaluator.metrics import summarize
from test.evaluator.failure_cases import infer_error_type, write_failure_case
from test.evaluator.report import create_run_report_dir, write_json_report, write_markdown_report
from test.evaluator.schemas import EvalCase, EvalCaseResult, EvalSummary
from test.evaluator.sql_utils import (
    aggregation_match,
    contains_all,
    extract_sql,
    result_set_f1,
    rows_equal,
    rows_semantically_equal,
    sql_exact_match,
)


class NL2SQLEvaluator:
    def __init__(self, cases: list[EvalCase], report_dir: Path):
        self.cases = cases
        self.report_dir = report_dir

    async def run(self) -> tuple[EvalSummary, list[EvalCaseResult]]:
        init_clients()
        results: list[EvalCaseResult] = []
        try:
            async with meta_mysql_client_manager.session_factory() as meta_session, dw_mysql_client_manager.session_factory() as dw_session:
                context = DataAgentContext(
                    embedding_client=embedding_client_manager.client,
                    column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client),
                    metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client),
                    value_es_repository=ValueESRepository(es_client_manager.client),
                    meta_mysql_repository=MetaMySQLRepository(meta_session),
                    dw_mysql_repository=DWMySQLRepository(dw_session),
                    trace_collector=None,
                )

                for case in self.cases:
                    results.append(await self._run_case(case, context))
        finally:
            await close_clients()

        summary = summarize(results)
        run_report_dir = create_run_report_dir(self.report_dir)
        write_json_report(run_report_dir, summary, results)
        write_markdown_report(run_report_dir, summary, results)
        return summary, results

    async def _run_case(self, case: EvalCase, context: DataAgentContext) -> EvalCaseResult:
        start = time.perf_counter()
        generated_sql: str | None = None
        gold_result: list[dict[str, Any]] | None = None
        generated_result: list[dict[str, Any]] | None = None
        syntax_valid = False
        execution_success = False
        strict_execution_accuracy = False
        execution_accuracy = False
        numeric_tolerance_accuracy = False
        result_f1 = 0.0
        error: str | None = None
        retrieval_latency_ms: float | None = None
        sql_generation_latency_ms: float | None = None
        sql_execution_latency_ms: float | None = None
        final_state: dict[str, Any] = {}
        trace_collector = TraceCollector()
        request_id = f"eval_{case.id}_{uuid.uuid4()}"

        try:
            state = DataAgentState(query=case.question)
            request_id_context_var.set(request_id)
            trace_collector.start_query(request_id=request_id, query=case.question, user_scope={}, source="evaluation")
            context["trace_collector"] = trace_collector
            final_state = await graph.ainvoke(input=state, context=context)
            generated_sql = extract_sql(final_state.get("sql"))
            state_error = final_state.get("error")
            if isinstance(state_error, str) and state_error.startswith("[EXCEED_STEP_LIMIT]"):
                error = state_error
                raise RuntimeError(state_error)

            gold_result = await context["dw_mysql_repository"].run(case.gold_sql)
            if generated_sql:
                await context["dw_mysql_repository"].validate(generated_sql)
                syntax_valid = True
                sql_execution_start = time.perf_counter()
                generated_result = await context["dw_mysql_repository"].run(generated_sql)
                trace_collector.set_execution_result(generated_result)
                sql_execution_latency_ms = (time.perf_counter() - sql_execution_start) * 1000
                execution_success = True
                strict_execution_accuracy = rows_equal(gold_result, generated_result)
                execution_accuracy = rows_semantically_equal(gold_result, generated_result, case.numeric_tolerance)
                numeric_tolerance_accuracy = execution_accuracy
                result_f1 = result_set_f1(gold_result, generated_result, case.numeric_tolerance)
            else:
                error = "未生成 SQL"
        except Exception as exc:
            error = str(exc)

        latency_ms = (time.perf_counter() - start) * 1000
        trace_collector.finish_query(final_sql=generated_sql, sql_valid=syntax_valid, error=error, total_latency_ms=latency_ms)
        trace_file = str(trace_collector.save_to_file())
        retrieval_traces = trace_collector.to_dict()["retrieval_traces"]
        retrieval_eval = evaluate_retrieval(case, final_state, retrieval_traces)
        filtering_eval = evaluate_filtering(case, final_state)
        result = EvalCaseResult(
            id=case.id,
            question=case.question,
            gold_sql=case.gold_sql,
            generated_sql=generated_sql,
            gold_result=gold_result,
            generated_result=generated_result,
            syntax_valid=syntax_valid,
            execution_success=execution_success,
            strict_execution_accuracy=strict_execution_accuracy,
            execution_accuracy=execution_accuracy,
            numeric_tolerance_accuracy=numeric_tolerance_accuracy,
            result_set_f1=result_f1,
            column_recall=retrieval_eval["column_recall"],
            column_precision=retrieval_eval["column_precision"],
            metric_recall=retrieval_eval["metric_recall"],
            value_recall=retrieval_eval["value_recall"],
            value_precision=retrieval_eval["value_precision"],
            table_recall=retrieval_eval["table_recall"],
            retrieval_metrics=retrieval_eval["retrieval_metrics"],
            retrieval_traces=retrieval_traces,
            filtered_table_accuracy=filtering_eval["filtered_table_accuracy"],
            filtered_column_accuracy=filtering_eval["filtered_column_accuracy"],
            context_compression_ratio=filtering_eval["context_compression_ratio"],
            context_loss_rate=filtering_eval["context_loss_rate"],
            sql_exact_match=sql_exact_match(generated_sql, case.gold_sql),
            table_match=contains_all(generated_sql, case.expected_tables),
            column_match=contains_all(generated_sql, case.expected_columns),
            condition_match=contains_all(generated_sql, case.expected_conditions),
            aggregation_match=aggregation_match(generated_sql, case.gold_sql),
            retrieval_latency_ms=retrieval_latency_ms,
            sql_generation_latency_ms=sql_generation_latency_ms,
            sql_execution_latency_ms=sql_execution_latency_ms,
            latency_ms=latency_ms,
            request_id=request_id,
            trace_file=trace_file,
            error=error,
            tags=case.tags,
        )
        result.error_type = infer_error_type(result)
        write_failure_case(case, result)
        return result


def evaluate_retrieval(case: EvalCase, state: dict[str, Any], retrieval_traces: list[dict[str, Any]]) -> dict[str, Any]:
    retrieved_columns = state.get("retrieved_columns") or []
    retrieved_metrics = state.get("retrieved_metrics") or []
    retrieved_values = state.get("retrieved_values") or []
    table_infos = state.get("table_infos") or []

    retrieved_column_names = collect_column_names(retrieved_columns)
    retrieved_metric_names = collect_metric_names(retrieved_metrics)
    retrieved_value_texts = collect_value_texts(retrieved_values)
    retrieved_table_names = collect_table_names_from_columns(retrieved_columns) | collect_table_names(table_infos)

    retrieval_metrics = calculate_topk_metrics(case, retrieval_traces)
    return {
        "column_recall": contains_expected(retrieved_column_names, case.expected_columns),
        "column_precision": precision(retrieved_column_names, case.expected_columns),
        "metric_recall": contains_expected(retrieved_metric_names, case.expected_metrics),
        "value_recall": contains_expected(retrieved_value_texts, case.expected_values),
        "value_precision": precision(retrieved_value_texts, case.expected_values),
        "table_recall": contains_expected(retrieved_table_names, case.expected_tables),
        "retrieval_metrics": retrieval_metrics,
    }


def calculate_topk_metrics(case: EvalCase, retrieval_traces: list[dict[str, Any]]) -> dict[str, float]:
    metrics: dict[str, dict[str, float]] = {
        "recall": {},
        "precision": {},
        "mrr": {},
    }
    node_specs = {
        "column_recall": ("column", case.expected_columns, [5, 10, 20]),
        "metric_recall": ("metric", case.expected_metrics, [3, 5]),
        "value_recall": ("value", case.expected_values, [3, 5]),
    }
    for node, (name, expected_items, top_k_values) in node_specs.items():
        candidates = flatten_trace_payloads(retrieval_traces, node)
        for k in top_k_values:
            metrics["recall"][f"{name}@{k}"] = recall_at_k(candidates, expected_items, k)
            metrics["precision"][f"{name}@{k}"] = precision_at_k(candidates, expected_items, k)
        metrics["mrr"][name] = mrr(candidates, expected_items)

    return metrics


def flatten_trace_payloads(retrieval_traces: list[dict[str, Any]], node: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for trace in retrieval_traces:
        if trace.get("node") != node:
            continue
        for result in trace.get("results", []):
            payload = result.get("payload", {})
            for text in payload_to_texts(payload):
                if text not in seen:
                    seen.add(text)
                    candidates.append(text)
    return candidates


def payload_to_texts(payload: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    for key in ["id", "name", "value", "column_name", "table_name", "table_id"]:
        value = payload.get(key)
        if value is not None and str(value).strip():
            texts.append(str(value).strip().lower())
    return texts


def recall_at_k(candidates: list[str], expected_items: list[str], k: int) -> float:
    if not expected_items:
        return 1.0
    top_k = set(candidates[:k])
    hits = sum(1 for expected in expected_items if item_in_set(expected, top_k))
    return round(hits / len(expected_items), 4)


def precision_at_k(candidates: list[str], expected_items: list[str], k: int) -> float:
    if not expected_items:
        return 1.0
    top_k = candidates[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for candidate in top_k if item_in_list(candidate, expected_items))
    return round(hits / len(top_k), 4)


def mrr(candidates: list[str], expected_items: list[str]) -> float:
    if not expected_items:
        return 1.0
    for index, candidate in enumerate(candidates, start=1):
        if item_in_list(candidate, expected_items):
            return round(1 / index, 4)
    return 0.0


def evaluate_filtering(case: EvalCase, state: dict[str, Any]) -> dict[str, Any]:
    retrieved_columns = state.get("retrieved_columns") or []
    table_infos = state.get("table_infos") or []
    filtered_table_names = collect_table_names(table_infos)
    filtered_column_names = collect_filtered_column_names(table_infos)
    retrieved_column_names = collect_column_names(retrieved_columns)

    retrieved_count = len(retrieved_column_names)
    filtered_count = len(filtered_column_names)
    compression_ratio = round(filtered_count / retrieved_count, 4) if retrieved_count else None
    lost_expected_columns = [column for column in case.expected_columns if not item_in_set(column, filtered_column_names)]

    return {
        "filtered_table_accuracy": contains_expected(filtered_table_names, case.expected_tables),
        "filtered_column_accuracy": contains_expected(filtered_column_names, case.expected_columns),
        "context_compression_ratio": compression_ratio,
        "context_loss_rate": round(len(lost_expected_columns) / len(case.expected_columns), 4) if case.expected_columns else 0.0,
    }


def collect_column_names(columns: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for column in columns:
        add_if_present(names, column.get("name"))
        add_if_present(names, column.get("id"))
    return names


def collect_metric_names(metrics: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for metric in metrics:
        add_if_present(names, metric.get("name"))
    return names


def collect_value_texts(values: list[dict[str, Any]]) -> set[str]:
    texts: set[str] = set()
    for value in values:
        add_if_present(texts, value.get("value"))
        add_if_present(texts, value.get("column_name"))
        add_if_present(texts, value.get("table_name"))
    return texts


def collect_table_names_from_columns(columns: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for column in columns:
        column_id = str(column.get("id", ""))
        if "." in column_id:
            names.add(column_id.split(".", 1)[0].lower())
        add_if_present(names, column.get("table_name"))
    return names


def collect_table_names(table_infos: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for table in table_infos:
        add_if_present(names, table.get("name"))
    return names


def collect_filtered_column_names(table_infos: list[dict[str, Any]]) -> set[str]:
    names: set[str] = set()
    for table in table_infos:
        table_name = str(table.get("name", "")).lower()
        for column in table.get("columns", []):
            column_name = str(column.get("name", "")).lower()
            add_if_present(names, column_name)
            if table_name and column_name:
                names.add(f"{table_name}.{column_name}")
    return names


def add_if_present(items: set[str], value: Any) -> None:
    if value is not None and str(value).strip():
        items.add(str(value).strip().lower())


def contains_expected(actual_items: set[str], expected_items: list[str]) -> bool:
    if not expected_items:
        return True
    return all(item_in_set(expected, actual_items) for expected in expected_items)


def precision(actual_items: set[str], expected_items: list[str]) -> float:
    if not expected_items:
        return 1.0
    if not actual_items:
        return 0.0
    expected_hit_count = sum(1 for item in actual_items if item_in_list(item, expected_items))
    return round(expected_hit_count / len(actual_items), 4)


def item_in_set(expected: str, actual_items: set[str]) -> bool:
    expected_text = expected.lower()
    return any(expected_text in actual or actual in expected_text for actual in actual_items)


def item_in_list(actual: str, expected_items: list[str]) -> bool:
    actual_text = actual.lower()
    return any(expected.lower() in actual_text or actual_text in expected.lower() for expected in expected_items)


def load_cases(path: Path, limit: int | None = None, tags: list[str] | None = None) -> list[EvalCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    cases = [EvalCase.from_dict(item) for item in raw_cases]
    if tags:
        tag_set = set(tags)
        cases = [case for case in cases if tag_set.intersection(case.tags)]
    if limit is not None:
        cases = cases[:limit]
    return cases


def init_clients() -> None:
    embedding_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()


async def close_clients() -> None:
    await qdrant_client_manager.close()
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()
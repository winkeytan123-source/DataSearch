from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.trace_collector import build_ranked_results
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


async def metric_recall(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回指标信息"})
    writer({"type": "progress", "step": "召回指标信息", "status": "running"})

    try:
        keywords = state['keywords']
        query = state['query']

        embedding_client = runtime.context["embedding_client"]
        metric_qdrant_repository = runtime.context["metric_qdrant_repository"]
        trace_collector = runtime.context.get("trace_collector")

        # 使用扩展后的关键词召回字段信息
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_metric_recall"),
                                input_variables=["query"])

        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        retrieved_metric_map: dict[str, MetricInfoQdrant] = {}

        keywords = list(set(keywords + result))

        for keyword in keywords:
            embedding = await embedding_client.aembed_query(keyword)
            search_results = await metric_qdrant_repository.search_with_score(embedding)
            payloads: list[MetricInfoQdrant] = [item["payload"] for item in search_results]
            if trace_collector:
                trace_collector.add_retrieval_trace(
                    node="metric_recall",
                    keyword=keyword,
                    channel="qdrant",
                    limit=20,
                    results=build_ranked_results(
                        [item["payload"] for item in search_results],
                        score_getter=lambda payload, result_map={item["payload"]["id"]: item["score"] for item in search_results}: result_map.get(payload["id"]),
                    ),
                )
            for payload in payloads:
                column_id = payload['id']
                if column_id not in retrieved_metric_map:
                    retrieved_metric_map[column_id] = payload

        retrieved_metric = list(retrieved_metric_map.values())
        logger.info(f"召回指标信息{list(retrieved_metric_map.keys())}")

        writer({"type": "progress", "step": "召回指标信息", "status": "success"})
        return {'retrieved_metrics': retrieved_metric}
    except Exception as e:
        logger.error(f"召回指标信息失败：{e}")
        writer({"type": "progress", "step": "召回指标信息", "status": "error"})
        raise


from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.trace_collector import build_ranked_results
from app.models.es.value_info_es import ValueInfoES
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


async def value_recall(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段值", "status": "running"})
    try:
        # 使用LLM扩展关键词
        keywords = state['keywords']
        query = state['query']

        value_es_repository = runtime.context["value_es_repository"]
        trace_collector = runtime.context.get("trace_collector")

        # 使用扩展后的关键词召回字段信息
        prompt = PromptTemplate(template=load_prompt("extend_keywords_for_value_recall"),
                                input_variables=["query"])

        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"query": query})

        value_map: dict[str, ValueInfoES] = {}

        keywords = list(set(keywords + result))

        for keyword in keywords:
            search_results = await value_es_repository.search_with_score(keyword)
            values: list[ValueInfoES] = [item["payload"] for item in search_results]
            if trace_collector:
                trace_collector.add_retrieval_trace(
                    node="value_recall",
                    keyword=keyword,
                    channel="elasticsearch",
                    limit=5,
                    results=build_ranked_results(
                        [item["payload"] for item in search_results],
                        score_getter=lambda payload, result_map={item["payload"]["id"]: item["score"] for item in search_results}: result_map.get(payload["id"]),
                    ),
                )
            for value in values:
                value_id = value['id']
                if value_id not in value_map:
                    value_map[value_id] = value

        retrieved_values = list(value_map.values())
        logger.info(f"召回字段取值{list(value_map.keys())}")

        writer({"type": "progress", "step": "召回字段值", "status": "success"})
        return {'retrieved_values': retrieved_values}
    except Exception as e:
        logger.error(f"召回字段值失败：{e}")
        writer({"type": "progress", "step": "召回字段值", "status": "error"})
        raise

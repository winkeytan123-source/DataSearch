import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.prompt.prompt_loader import load_prompt
from app.core.log import logger


MAX_SQL_CORRECTION_COUNT = 3


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校正SQL", "status": "running"})

    try:
        correction_count = state.get("sql_correction_count", 0)
        if correction_count >= MAX_SQL_CORRECTION_COUNT:
            error = (
                f"[EXCEED_STEP_LIMIT] SQL 更正次数已达到上限 {MAX_SQL_CORRECTION_COUNT} 次，仍未通过校验；"
                f"current_count={correction_count}; last_error={state.get('error')}"
            )
            logger.error(error)
            writer({"type": "error", "message": error})
            writer({"type": "progress", "step": "校正SQL", "status": "error"})
            return {"error": error}

        table_infos = state['table_infos']
        metric_infos = state['metric_infos']
        date_info = state['date_info']
        db_info = state['db_info']
        query = state['query']
        sql = state["sql"]
        error = state['error']

        dw_mysql_repository = runtime.context['dw_mysql_repository']

        prompt = PromptTemplate(template=load_prompt("correct_sql"),
                                input_variables=["table_infos", "metric_infos", "date_info", "db_info", "query", "sql",
                                                 "error"])

        output_parser = StrOutputParser()

        chain = prompt | llm | output_parser

        result = await chain.ainvoke({"table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
                                      "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
                                      "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                                      "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
                                      "query": query,
                                      "sql": sql,
                                      "error": error})

        writer({"type": "progress", "step": "校正SQL", "status": "success"})
        logger.info(f"修正的SQL语句：{result}")

        return {"sql": result, "sql_correction_count": correction_count + 1}
    except Exception as e:
        logger.error(f"校正SQL失败：{e}")
        writer({"type": "progress", "step": "校正SQL", "status": "error"})
        raise

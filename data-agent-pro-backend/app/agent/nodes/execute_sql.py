from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL", "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository = runtime.context['dw_mysql_repository']
        result = await dw_mysql_repository.run(sql)
        logger.info(f"SQL执行结果：{result}")
        writer({"type": "progress", "step": "执行SQL", "status": "success"})
        writer({"type": "result", "data": result})
    except Exception as e:
        logger.error(f"SQL执行失败：{e}")
        writer({"type": "progress", "step": "执行SQL", "status": "error"})
        raise

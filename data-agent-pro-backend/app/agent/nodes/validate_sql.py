from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "验证SQL语句", "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository = runtime.context['dw_mysql_repository']

        try:
            await dw_mysql_repository.validate(sql)
            logger.info("SQL语句正确")
            writer({"type": "progress", "step": "验证SQL语句", "status": "success"})
            return {"error": None}
        except Exception as e:
            logger.info(f"SQL语句错误：{e}")
            writer({"type": "progress", "step": "验证SQL语句", "status": "success"})
            return {'error': str(e)}
    except Exception as e:
        logger.error(f"验证SQL语句失败：{e}")
        writer({"type": "progress", "step": "验证SQL语句", "status": "error"})
        raise

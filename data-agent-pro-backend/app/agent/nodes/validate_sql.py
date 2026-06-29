from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
from app.core.sql_security import validate_select_sql_security


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "验证SQL语句", "status": "running"})

    try:
        sql = state["sql"]
        table_infos = state.get("table_infos") or []
        dw_mysql_repository = runtime.context['dw_mysql_repository']
        trace_collector = runtime.context.get("trace_collector")

        try:
            security_result = validate_select_sql_security(sql, table_infos)
            if not security_result.valid:
                security_error = security_result.error or "SQL 安全校验失败"
                if trace_collector:
                    trace_collector.set_sql_validation(sql, valid=False, error=f"[AST_SECURITY] {security_error}")
                raise ValueError(f"[AST_SECURITY] {security_error}")

            await dw_mysql_repository.validate(sql)
            if trace_collector:
                trace_collector.set_sql_validation(sql, valid=True)
            logger.info("SQL语句正确")
            writer({"type": "progress", "step": "验证SQL语句", "status": "success"})
            return {"error": None}
        except Exception as e:
            if trace_collector:
                trace_collector.set_sql_validation(sql, valid=False, error=str(e))
            logger.info(f"SQL语句错误：{e}")
            writer({"type": "progress", "step": "验证SQL语句", "status": "success"})
            return {'error': str(e)}
    except Exception as e:
        logger.error(f"验证SQL语句失败：{e}")
        writer({"type": "progress", "step": "验证SQL语句", "status": "error"})
        raise

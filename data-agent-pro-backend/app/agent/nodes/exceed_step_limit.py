from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


MAX_SQL_CORRECTION_COUNT = 3


async def exceed_step_limit(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    error = state.get("error") or "未知 SQL 校验错误"
    correction_count = state.get("sql_correction_count", 0)
    message = (
        f"[EXCEED_STEP_LIMIT] SQL 更正次数已达到上限 "
        f"{MAX_SQL_CORRECTION_COUNT} 次，仍未通过校验；"
        f"current_count={correction_count}; last_error={error}"
    )
    logger.error(message)
    writer({"type": "progress", "step": "校正SQL", "status": "error"})
    writer({"type": "error", "message": message})
    raise RuntimeError(message)

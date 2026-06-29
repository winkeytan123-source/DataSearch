import json
import uuid

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.core.context import request_id_context_var
from app.core.failure_case import write_online_failure_case
from app.core.log import logger
from app.core.trace_collector import TraceCollector
from app.repository.es.value_es_repository import ValueESRepository
from app.repository.mysql.dw_mysql_repository import DWMySQLRepository
from app.repository.mysql.meta_mysql_repository import MetaMySQLRepository
from app.repository.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repository.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService():
    def __init__(self,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 column_qdrant_repository: ColumnQdrantRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 value_es_repository: ValueESRepository,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository):
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

    async def query(self, query: str):
        state = DataAgentState(query=query)
        request_id = str(uuid.uuid4())
        request_id_context_var.set(request_id)
        trace_collector = TraceCollector()
        trace_collector.start_query(request_id=request_id, query=query, user_scope={}, source="online")
        context = DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
            trace_collector=trace_collector,
        )
        final_error: str | None = None
        try:
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                if isinstance(chunk, dict):
                    if chunk.get("type") == "result":
                        trace_collector.set_execution_result(chunk.get("data"))
                    elif chunk.get("type") == "error":
                        final_error = chunk.get("message")
                yield f"data:{json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            final_error = str(e)
            error = {"type": "error", "message": str(e)}
            yield f"data:{json.dumps(error, ensure_ascii=False, default=str)}\n\n"
        finally:
            trace_collector.finish_query(error=final_error)
            trace_collector.save_to_file()
            # 在线数据飞轮：查询失败时自动沉淀失败样例
            failure_path = write_online_failure_case(trace_collector, final_error)
            if failure_path:
                logger.info(f"数据飞轮：失败样例已沉淀 -> {failure_path}")

import asyncio
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio.engine import AsyncEngine

from app.config.app_config import DBConfig, app_config


class MysqlClientManager:
    def __init__(self, db_config: DBConfig):
        self.db_config = db_config
        self.engine: Optional[AsyncEngine, None] = None
        self.session_factory = None

    def _get_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"

    def init(self):
        # pool_pre_ping参数设置为True（启用连接池“预ping”功能），在 SQLAlchemy 的连接池中，pool_pre_ping 用于在每次从连接池中获取连接之前，先检查连接是否仍然有效。
        # 好处：防止使用失效连接：避免在执行数据库操作时遇到连接已断开的错误（连接长时间不用，服务端会自动断开）
        self.engine = create_async_engine(self._get_url(), pool_size=10, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, autoflush=True,
                                                  expire_on_commit=False)

    async def close(self):
        await self.engine.dispose()


dw_mysql_client_manager = MysqlClientManager(app_config.db_dw)

meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    dw_mysql_client_manager.init()


    # 采用sessionmaker简化代码
    async def test():
        # 异步场景下，session中的expire_on_commit参数要设置为False（同步一般为True），commit后函数中的属性不过期
        async with dw_mysql_client_manager.session_factory() as session:
            result = await session.execute(text("select * from fact_order limit 10"))
            # mapping用于指定返回的形式是mapping
            rows = result.mappings().fetchall()
            print(rows[0])


    asyncio.run(test())

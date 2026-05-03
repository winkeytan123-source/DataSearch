import sys
import uuid
from pathlib import Path

from loguru import logger

from app.config.app_config import app_config
from app.core.context import request_id_context_var

# 在FastAPI中，request_id是为了区分不同Task的执行情况，在日志中便于区分它们（request_id参数本身不存在，需要在添加好的extra中获取，即extra[request_id]）
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<magenta>request_id - {extra[request_id]}</magenta> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def inject_request_id(record):
    try:
        # 在FastAPI中，可以使用中间件提前进行获取，为什么要try?
        # 在命令行中执行脚本时，没有中间件进行提前get，因此未必能获取到request_id
        request_id = request_id_context_var.get()
    except Exception as e:
        request_id = uuid.uuid4()
    record["extra"]["request_id"] = request_id


logger.remove()
logger = logger.patch(inject_request_id)
if app_config.logging.console.enable:
    # sys.stdout表示标准输出（输出到控制台）
    logger.add(sink=sys.stdout, level=app_config.logging.console.level, format=log_format)
if app_config.logging.file.enable:
    path = Path(app_config.logging.file.path)
    path.mkdir(parents=True, exist_ok=True)
    logger.add(
        sink=path / "app.log",
        level=app_config.logging.file.level,
        format=log_format,
        rotation=app_config.logging.file.rotation,
        retention=app_config.logging.file.retention,
        encoding="utf-8"
    )

if __name__ == '__main__':
    logger.info("hello world")

from email.policy import default

from sentry_sdk.utils import ContextVar

# contextvars可以在每个异步任务上下文中设置变量
request_id_context_var: ContextVar[str] = ContextVar("request_id", default="1")

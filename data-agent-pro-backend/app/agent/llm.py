import os

from langchain.chat_models import init_chat_model

from app.config.app_config import app_config

llm = init_chat_model(model=app_config.llm.model_name,
                      base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                      model_provider="openai",
                      api_key=os.getenv("DASHSCOPE_API_KEY"),
                      temperature=0)

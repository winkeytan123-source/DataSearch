from typing import TypeVar, Type

from omegaconf import OmegaConf
from pathlib import Path

# 类型参数
T = TypeVar("T")


def load_config(config_path: Path, schema_cls: Type[T]) -> T:
    context = OmegaConf.load(config_path)
    schema = OmegaConf.structured(schema_cls)
    config: T = OmegaConf.to_object(OmegaConf.merge(schema, context))
    return config

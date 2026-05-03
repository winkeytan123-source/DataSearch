from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from omegaconf import OmegaConf

from app.config.config_loader import load_config


@dataclass
class ColumnConfig:
    name: str
    role: str
    description: str
    alias: list[str]
    sync: bool


@dataclass
class TableConfig:
    name: str
    role: str
    description: str
    columns: list[ColumnConfig]


@dataclass
class MetricConfig:
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


@dataclass
class MetaConfig:
    tables: Optional[list[TableConfig]]
    metrics: Optional[list[MetricConfig]]


config_file = Path(__file__).parents[2] / 'conf' / 'meta_config.yaml'

meta_config: MetaConfig = load_config(config_file, MetaConfig)

if __name__ == '__main__':
    print(meta_config.metrics[0].name)
